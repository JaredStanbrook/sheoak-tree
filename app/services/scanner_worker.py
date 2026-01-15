import logging
import platform
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from zeroconf import ServiceBrowser, Zeroconf

logger = logging.getLogger(__name__)


class MDNSListener:
    """Maintains a cache of mDNS services for hostname resolution."""

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
            server = info.server.replace(".local.", "")
            self.hostnames[ip] = server

            if ip not in self.services:
                self.services[ip] = set()
            self.services[ip].add(type)

            if info.properties:
                props = {
                    k.decode() if isinstance(k, bytes) else k: v.decode()
                    if isinstance(v, bytes)
                    else v
                    for k, v in info.properties.items()
                }
                self.device_info[ip] = props
        except Exception:
            pass

    def add_service(self, zc, type, name):
        self.update_service(zc, type, name)

    def remove_service(self, zc, type, name):
        pass  # Optional: Implement expiration logic if needed

    def update_record(self, zc, now, record):
        pass


class NetworkDiscovery:
    """
    Replaces SNMP with Active Ping Sweep + Local ARP Table lookup.
    Thread-safe and synchronous to match the application architecture.
    """

    def __init__(self, target_gateway):
        self.subnet_prefix = ".".join(target_gateway.split(".")[:3])
        self.is_windows = platform.system().lower() == "windows"

    def _ping_host(self, ip):
        """Pings a single host. Returns IP if up, None otherwise."""
        try:
            # Use appropriate flag for count (-n for Windows, -c for Linux/Mac)
            param = "-n" if self.is_windows else "-c"
            timeout_param = "-w" if self.is_windows else "-W"
            # 1 packet, 1 second timeout (fast scan)
            cmd = ["ping", param, "1", timeout_param, "1", ip]

            ret = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return ip if ret.returncode == 0 else None
        except Exception:
            return None

    def scan_subnet(self):
        """
        Active Phase: Ping all hosts in /24 subnet to populate local ARP cache.
        Uses ThreadPool for speed.
        """
        active_ips = []
        # Create list of all 254 IPs
        ips_to_scan = [f"{self.subnet_prefix}.{i}" for i in range(1, 255)]

        # Max workers 50 ensures scan finishes in < 5 seconds
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(self._ping_host, ip): ip for ip in ips_to_scan}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    active_ips.append(result)
        return active_ips

    def get_arp_table(self):
        """
        Passive Phase: Read system ARP table to map IP -> MAC.
        Works on Linux (standard for Pi) and macOS/Windows via parsing.
        """
        arp_map = {}

        try:
            # Linux Optimization: Read /proc/net/arp directly if available
            if not self.is_windows:
                try:
                    with open("/proc/net/arp", "r") as f:
                        # Skip header
                        next(f)
                        for line in f:
                            parts = line.split()
                            if len(parts) >= 4:
                                ip = parts[0]
                                mac = parts[3]
                                # Filter incomplete or loopback entries
                                if mac != "00:00:00:00:00:00" and len(mac) == 17:
                                    arp_map[ip] = mac.upper()
                    return arp_map
                except FileNotFoundError:
                    pass  # Fallback to CLI command

            # Cross-platform fallback: arp -a
            cmd = ["arp", "-a"]
            output = subprocess.check_output(cmd).decode()

            # Regex for IP (IPv4) and MAC
            # Matches (192.168.1.1) at ... 00:11:22:33:44:55
            for line in output.splitlines():
                # Extract IP
                ip_match = re.search(r"\(?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)?", line)
                # Extract MAC
                mac_match = re.search(
                    r"([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})",
                    line,
                )

                if ip_match and mac_match:
                    ip = ip_match.group(1)
                    mac = mac_match.group(1).replace("-", ":").upper()
                    arp_map[ip] = mac

        except Exception as e:
            logger.error(f"ARP Table Read Error: {e}")

        return arp_map


# --- Main Worker Entry Point ---


def scanner_process_entry(target_ip, community, interval, queue, stop_event):
    """
    Worker process entry point.
    Runs active discovery loop.
    (Note: 'community' arg kept for signature compatibility but ignored)
    """
    logger.info("Network Scanner Process Started (Method: Active Ping + ARP)")

    # 1. Initialize mDNS (Passive Discovery)
    zc = Zeroconf()
    listener = MDNSListener()
    # Browse common service types to enrich data
    ServiceBrowser(
        zc,
        [
            "_googlecast._tcp.local.",
            "_airplay._tcp.local.",
            "_http._tcp.local.",
            "_device-info._tcp.local.",
            "_workstation._tcp.local.",
        ],
        listener,
    )

    # 2. Initialize Scanner (Active Discovery)
    scanner = NetworkDiscovery(target_ip)

    try:
        while not stop_event.is_set():
            start_time = time.time()

            try:
                # A. Active Scan (Populate ARP Cache)
                # We don't necessarily need the returned list of IPs because
                # we rely on the ARP table for the final MAC mapping.
                scanner.scan_subnet()

                # B. Read ARP Table (The Source of Truth)
                arp_data = scanner.get_arp_table()

                # C. Enrich Data
                batch = []
                for ip, mac in arp_data.items():
                    # Check randomized MAC (Locally Administered Bit)
                    is_random = False
                    if len(mac) == 17:
                        # 2nd char of 1st byte: 2, 6, A, E
                        second_char = mac[1].upper()
                        is_random = second_char in ["2", "6", "A", "E"]

                    device = {
                        "mac": mac,
                        "ip": ip,
                        "is_random": is_random,
                        "hostname": listener.hostnames.get(ip),
                        "mdns_services": list(listener.services.get(ip, [])),
                        "device_info": listener.device_info.get(ip, {}),
                    }
                    batch.append(device)

                # D. Send to Main Process
                if batch:
                    queue.put(batch)

            except Exception as e:
                logger.error(f"Scanner Loop Error: {e}")

            # Sleep Logic
            elapsed = time.time() - start_time
            sleep_time = max(1, interval - elapsed)

            # Check stop event periodically during long sleeps
            if sleep_time > 5:
                for _ in range(int(sleep_time)):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
            else:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        zc.close()
        logger.info("Scanner Process Exiting")
