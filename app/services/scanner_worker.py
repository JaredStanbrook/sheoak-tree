import asyncio
import logging
import os
import socket
from datetime import datetime

# --- Strict Imports (Modern v3arch) ---
try:
    # As per your provided docs: using v3arch.asyncio
    from pysnmp.hlapi.v3arch.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        walk_cmd,
    )
    from zeroconf import ServiceBrowser, Zeroconf
except ImportError as e:
    raise ImportError(
        f"Missing dependencies. Run: pip install 'pysnmp>=7.0' zeroconf netaddr. Error: {e}"
    )

logger = logging.getLogger(__name__)

# --- Helper Functions ---


def is_randomized_mac(mac):
    """Checks the Locally Administered Bit (2nd char)"""
    if len(mac) < 2:
        return False
    second_char = mac[1].upper()
    return second_char in ["2", "6", "A", "E"]


async def fetch_arp_table(target_ip, community):
    """Fetch ARP table via SNMP (v3arch compliant)"""
    arp_map = {}

    try:
        # 1. Create the SNMP Engine
        snmp_engine = SnmpEngine()

        # 2. Create Transport Target ASYNCHRONOUSLY (Critical Fix)
        # Your docs show: await UdpTransportTarget.create(...)
        transport = await UdpTransportTarget.create((target_ip, 161), timeout=2.0, retries=1)

        # 3. Define the OID for ARP table (IP-NetToMedia-PhysAddress)
        oid = "1.3.6.1.2.1.4.22.1.2"

        # 4. Run the Walk Command
        iterator = walk_cmd(
            snmp_engine,
            CommunityData(community),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        )

        # 5. Iterate results
        async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if errorIndication or errorStatus:
                continue

            for varBind in varBinds:
                try:
                    # Parse IP from OID suffix
                    # OID format: ...1.3.6.1.2.1.4.22.1.2.{interface_index}.{ip_1}.{ip_2}.{ip_3}.{ip_4}
                    ip_parts = varBind[0].getOid().asTuple()[-4:]
                    ip_addr = ".".join(str(x) for x in ip_parts)

                    # Parse MAC bytes
                    mac_bytes = varBind[1].asNumbers()
                    if len(mac_bytes) == 6:
                        mac_str = ":".join([f"{b:02X}" for b in mac_bytes])
                        arp_map[ip_addr] = mac_str
                except Exception:
                    continue

        # Close the dispatcher to free resources
        snmp_engine.close_dispatcher()

    except Exception as e:
        logger.error(f"SNMP Error: {e}")

    return arp_map


async def detect_os_by_ttl(ip):
    """Detect OS via TTL (Linux/Mac=64, Win=128)"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="ignore").lower()

        if "ttl=" in output:
            val = output.split("ttl=")[1].split()[0]
            ttl = int(val)
            if ttl <= 64:
                return "unix-like"
            if ttl <= 128:
                return "windows"
    except:
        pass
    return None


async def quick_port_scan(ip):
    """Check specific ports to ID device type"""
    ports = {22: "ssh", 80: "http", 443: "https", 445: "smb", 548: "afp", 5000: "upnp"}
    open_ports = []

    async def check(p):
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(ip, p), 0.5)
            writer.close()
            await writer.wait_closed()
            return p
        except:
            return None

    results = await asyncio.gather(*[check(p) for p in ports], return_exceptions=True)
    for res in results:
        if res:
            open_ports.append(ports[res])
    return open_ports


# --- mDNS Listener ---


class MDNSCache:
    def __init__(self):
        self.hostnames = {}
        self.services = {}
        self.device_info = {}

    def update_service(self, zc, type, name):
        try:
            info = zc.get_service_info(type, name)
            if not info or not info.addresses:
                return

            ip = socket.inet_ntoa(info.addresses[0])
            self.hostnames[ip] = info.server.replace(".local.", "")

            if ip not in self.services:
                self.services[ip] = set()
            self.services[ip].add(type)

            if info.properties:
                props = {
                    k.decode("utf-8") if isinstance(k, bytes) else k: v.decode("utf-8")
                    if isinstance(v, bytes)
                    else v
                    for k, v in info.properties.items()
                }
                self.device_info[ip] = props
        except:
            pass

    def add_service(self, zc, type, name):
        self.update_service(zc, type, name)

    def remove_service(self, *args):
        pass

    def update_record(self, *args):
        pass


# --- Main Worker Loop ---


async def scan_loop(target_ip, community, interval, queue, stop_event):
    logger.info(f"Scanner Worker Started (PID: {os.getpid()})")

    zc = Zeroconf()
    mdns_cache = MDNSCache()
    browsers = []

    service_types = [
        "_device-info._tcp.local.",
        "_workstation._tcp.local.",
        "_airplay._tcp.local.",
        "_googlecast._tcp.local.",
        "_http._tcp.local.",
    ]

    for st in service_types:
        browsers.append(ServiceBrowser(zc, st, mdns_cache))

    while not stop_event.is_set():
        try:
            # 1. Get Base ARP Data
            arp_data = await fetch_arp_table(target_ip, community)

            # 2. Enrich Data
            batch_results = []

            async def enrich_device(ip, mac):
                # Random checks to save resources (10% chance for deep scan)
                do_deep_scan = (hash(mac + str(datetime.now())) % 10) == 0

                return {
                    "mac": mac,
                    "ip": ip,
                    "is_random": is_randomized_mac(mac),
                    "hostname": mdns_cache.hostnames.get(ip),
                    "mdns_services": list(mdns_cache.services.get(ip, [])),
                    "device_info": mdns_cache.device_info.get(ip, {}),
                    "os_guess": await detect_os_by_ttl(ip) if do_deep_scan else None,
                    "open_ports": await quick_port_scan(ip) if do_deep_scan else None,
                }

            tasks = [enrich_device(ip, mac) for ip, mac in arp_data.items()]
            if tasks:
                batch_results = await asyncio.gather(*tasks)
                queue.put(batch_results)

        except Exception as e:
            logger.error(f"Scan Loop Error: {e}")

        # Sleep with check
        for _ in range(interval):
            if stop_event.is_set():
                break
            await asyncio.sleep(1)

    zc.close()


def scanner_process_entry(target_ip, community, interval, queue, stop_event):
    """Multiprocessing entry point"""
    try:
        asyncio.run(scan_loop(target_ip, community, interval, queue, stop_event))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Critical Scanner Failure: {e}", exc_info=True)
