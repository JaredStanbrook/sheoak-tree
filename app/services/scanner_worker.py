import asyncio
import logging
import socket

# Configure logging for the isolated process
logging.basicConfig(level=logging.INFO, format="[Scanner] %(message)s")
logger = logging.getLogger("Scanner")


def scanner_process_entry(target_ip, community, scan_interval, output_queue, stop_event):
    """
    Entry point for the isolated scanner process.
    This runs in a pristine Python environment (no Gevent, no Flask).
    """
    try:
        asyncio.run(
            run_async_scan_loop(target_ip, community, scan_interval, output_queue, stop_event)
        )
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Critical Scanner Failure: {e}")


async def run_async_scan_loop(target_ip, community, scan_interval, output_queue, stop_event):
    # Import locally to avoid top-level side effects
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

    # --- mDNS Helper ---
    class MDNSListener:
        def __init__(self):
            self.cache = {}

        def remove_service(self, zc, type, name):
            pass

        def add_service(self, zc, type, name):
            pass

        def update_service(self, zc, type, name):
            try:
                info = zc.get_service_info(type, name)
                if info and info.addresses:
                    ip = socket.inet_ntoa(info.addresses[0])
                    clean = info.server.replace(".local.", "")
                    self.cache[ip] = clean
            except:
                pass

    # --- SNMP Helper ---
    async def fetch_arp_table():
        arp_map = {}
        try:
            transport = await UdpTransportTarget.create((target_ip, 161), timeout=2.0, retries=1)
            iterator = walk_cmd(
                SnmpEngine(),
                CommunityData(community),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.4.22.1.2")),
                lexicographicMode=False,
            )
            async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication or errorStatus:
                    continue
                for varBind in varBinds:
                    try:
                        # OID: ...1.3.6.1.2.1.4.22.1.2.INTERFACE.IP.IP.IP.IP
                        ip_parts = varBind[0].getOid().asTuple()[-4:]
                        ip_addr = ".".join(str(x) for x in ip_parts)
                        mac_bytes = varBind[1].asNumbers()
                        if len(mac_bytes) == 6:
                            mac_str = ":".join([f"{b:02X}" for b in mac_bytes])
                            arp_map[ip_addr] = mac_str
                    except:
                        pass
            return arp_map
        except Exception:
            return {}

    # --- Main Loop ---
    mdns = MDNSListener()
    zc = Zeroconf()
    ServiceBrowser(zc, ["_device-info._tcp.local.", "_workstation._tcp.local."], mdns)

    logger.info(f"Scanner active. Polling {target_ip} every {scan_interval}s")

    while not stop_event.is_set():
        try:
            arp_data = await fetch_arp_table()
            results = []
            for ip, mac in arp_data.items():
                results.append(
                    {
                        "mac": mac,
                        "ip": ip,
                        "hostname": mdns.cache.get(ip),
                        "is_random": (len(mac) > 1 and mac[1] in ["2", "6", "A", "E"]),
                    }
                )

            if results:
                output_queue.put(results)

        except Exception as e:
            logger.error(f"Scan cycle error: {e}")

        # Non-blocking sleep loop to catch stop_event
        for _ in range(scan_interval):
            if stop_event.is_set():
                break
            await asyncio.sleep(1)

    zc.close()
    logger.info("Scanner stopped.")
