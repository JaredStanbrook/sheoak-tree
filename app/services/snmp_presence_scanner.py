import asyncio
import logging
import time
from typing import Dict, List, Optional

from pysnmp.hlapi.asyncio import (  # type: ignore[import-untyped]
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    walk_cmd,
)

from app.services.core import ThreadedService

logger = logging.getLogger(__name__)


class SnmpPresenceScanner(ThreadedService):
    """Poll SNMP client tables and feed results into the PresenceMonitor."""

    def __init__(self, app, target_ip: str, community: str, interval: int = 60):
        super().__init__("SnmpPresenceScanner", interval=interval)
        self.app = app
        self.target_ip = target_ip
        self.community = community
        self._snmp_engine = SnmpEngine()

    def run(self):
        try:
            clients = asyncio.run(self._poll_clients())
        except RuntimeError:
            clients = asyncio.new_event_loop().run_until_complete(self._poll_clients())
        except Exception as e:
            logger.error(f"SNMP poll failed: {e}", exc_info=True)
            return

        if not clients:
            return

        presence_monitor = self.app.service_manager.get_service("PresenceMonitor")
        if not presence_monitor:
            logger.warning("PresenceMonitor not available; SNMP results skipped")
            return

        try:
            presence_monitor.ingest_snmp_clients(clients)
        except Exception as e:
            logger.error(f"Failed to ingest SNMP clients: {e}", exc_info=True)

    async def _poll_clients(self) -> List[Dict[str, str]]:
        config = self.app.config
        phys_oid = config.get("SNMP_IPNETTOMEDIA_PHYS_OID")
        net_oid = config.get("SNMP_IPNETTOMEDIA_NET_OID")

        if not phys_oid or not net_oid:
            logger.warning("SNMP OIDs not configured; skipping poll")
            return []

        start = time.time()
        macs = await self._walk_oid(phys_oid)
        ips = await self._walk_oid(net_oid)

        hostname_table = await self._walk_optional(config.get("SNMP_CLIENT_HOSTNAME_OID"))
        signal_table = await self._walk_optional(config.get("SNMP_CLIENT_SIGNAL_OID"))
        band_table = await self._walk_optional(config.get("SNMP_CLIENT_BAND_OID"))

        clients: List[Dict[str, str]] = []
        for suffix, mac_value in macs.items():
            ip_value = ips.get(suffix)
            mac = self._format_mac(mac_value)
            if not ip_value or not mac:
                continue

            client = {
                "mac": mac,
                "ip": str(ip_value),
            }

            hostname = hostname_table.get(suffix)
            signal = signal_table.get(suffix)
            band = band_table.get(suffix)

            if hostname:
                client["hostname"] = str(hostname)
            if signal:
                client["signal_dbm"] = str(signal)
            if band:
                client["band"] = str(band)

            clients.append(client)

        elapsed = time.time() - start
        logger.debug(f"SNMP poll returned {len(clients)} clients in {elapsed:.2f}s")
        return clients

    async def _walk_optional(self, oid: Optional[str]) -> Dict[str, str]:
        if not oid:
            return {}
        return await self._walk_oid(oid)

    async def _walk_oid(self, oid: str) -> Dict[str, str]:
        results: Dict[str, str] = {}
        try:
            target = await UdpTransportTarget.create(
                (self.target_ip, 161),
                timeout=2.0,
                retries=1,
            )
        except Exception as e:
            logger.error(f"SNMP transport setup failed: {e}", exc_info=True)
            return results

        community = CommunityData(self.community, mpModel=1)

        async for error_indication, error_status, error_index, var_binds in walk_cmd(
            self._snmp_engine,
            community,
            target,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        ):
            if error_indication:
                logger.warning(f"SNMP error: {error_indication}")
                break
            if error_status:
                logger.warning(
                    "SNMP error status: %s at %s",
                    error_status.prettyPrint(),
                    error_index and var_binds[int(error_index) - 1][0] or "?",
                )
                break

            for name, val in var_binds:
                suffix = self._suffix_for(name.prettyPrint(), oid)
                if suffix is None:
                    continue
                results[suffix] = val

        return results

    @staticmethod
    def _suffix_for(full_oid: str, base_oid: str) -> Optional[str]:
        prefix = f"{base_oid}."
        if not full_oid.startswith(prefix):
            return None
        return full_oid[len(prefix) :]

    @staticmethod
    def _format_mac(value) -> Optional[str]:
        try:
            raw = value.asOctets()
        except Exception:
            return None
        if not raw:
            return None
        return ":".join(f"{b:02X}" for b in raw)
