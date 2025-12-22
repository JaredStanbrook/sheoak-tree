# app/services/presence_monitor.py
import time
import threading
import logging
from datetime import datetime, timedelta
from pysnmp.hlapi import *
from app.extensions import socketio, db
from app.models import Device, PresenceEvent

logger = logging.getLogger(__name__)


class PresenceMonitor:
    """
    Monitors network presence by querying a router's ARP table via SNMP.
    Detects when known devices (phones, laptops) connect/disconnect from the network.
    """

    def __init__(self, app, target_ip, community, scan_interval=60):
        self.app = app
        self.target_ip = target_ip
        self.community = community
        self.scan_interval = scan_interval
        self.socketio = socketio
        self._lock = threading.Lock()
        
        # Runtime state
        self.monitoring = True
        self.last_scan_time = None
        
        # Start background monitoring thread
        self.monitor_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"PresenceMonitor initialized - scanning {target_ip} every {scan_interval}s")

    def _scan_loop(self):
        """Background thread that periodically scans for active devices"""
        logger.info("Starting Presence Monitor scan loop")
        
        while self.monitoring:
            try:
                self.last_scan_time = datetime.now()
                active_macs = self.get_active_macs()
                
                if active_macs is not None:
                    self._process_presence(active_macs)
                else:
                    logger.warning("Failed to retrieve active MACs from router")
                
                time.sleep(self.scan_interval)
                
            except Exception as e:
                logger.error(f"Error in presence scan loop: {e}")
                time.sleep(self.scan_interval)

    def get_active_macs(self):
        """
        Query router via SNMP to get list of active MAC addresses.
        Uses OID 1.3.6.1.2.1.4.22.1.2 (ipNetToMediaPhysAddress) from the ARP table.
        
        Returns:
            set: Set of MAC addresses in format 'AA:BB:CC:DD:EE:FF', or None on error
        """
        try:
            active_macs = set()
            
            # SNMP Walk to get ARP table entries
            # OID 1.3.6.1.2.1.4.22.1.2 = ipNetToMediaPhysAddress (MAC addresses in ARP table)
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.target_ip, 161), timeout=2, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity('1.3.6.1.2.1.4.22.1.2')),
                lexicographicMode=False
            ):
                
                if errorIndication:
                    logger.error(f"SNMP error: {errorIndication}")
                    return None
                    
                elif errorStatus:
                    logger.error(f"SNMP error: {errorStatus.prettyPrint()}")
                    return None
                    
                else:
                    for varBind in varBinds:
                        # Extract MAC address from the response
                        # The value is typically returned as a hex string or byte string
                        mac_bytes = varBind[1].asNumbers()
                        
                        # Convert to standard MAC format (AA:BB:CC:DD:EE:FF)
                        if len(mac_bytes) == 6:
                            mac_address = ':'.join([f'{b:02X}' for b in mac_bytes])
                            active_macs.add(mac_address)
            
            logger.info(f"Found {len(active_macs)} active devices on network")
            return active_macs
            
        except Exception as e:
            logger.error(f"Error querying SNMP: {e}")
            return None

    def _process_presence(self, active_macs):
        """
        Compare active MACs with database and update presence status.
        
        Args:
            active_macs (set): Set of MAC addresses currently active on network
        """
        with self.app.app_context():
            try:
                # Get all registered devices
                devices = Device.query.all()
                
                for device in devices:
                    was_home = device.is_home
                    is_now_home = device.mac_address in active_macs
                    
                    # State change detected
                    if was_home != is_now_home:
                        self._handle_presence_change(device, is_now_home)
                    
                    # Update last_seen for devices that are present
                    elif is_now_home:
                        device.last_seen = datetime.now()
                        db.session.commit()
                
            except Exception as e:
                logger.error(f"Error processing presence: {e}")
                db.session.rollback()

    def _handle_presence_change(self, device, is_now_home):
        """
        Handle a device arriving or leaving.
        
        Args:
            device (Device): The device that changed state
            is_now_home (bool): True if device arrived, False if left
        """
        now = datetime.now()
        event_type = "arrived" if is_now_home else "left"
        
        # Update device status
        device.is_home = is_now_home
        device.last_seen = now if is_now_home else device.last_seen
        
        # Log the event
        presence_event = PresenceEvent(
            device_id=device.id,
            event_type=event_type,
            timestamp=now
        )
        
        db.session.add(presence_event)
        db.session.commit()
        
        # Emit real-time update via SocketIO
        self.socketio.emit('presence_update', {
            'device_id': device.id,
            'device_name': device.name,
            'owner': device.owner,
            'event_type': event_type,
            'is_home': is_now_home,
            'timestamp': now.isoformat()
        })
        
        logger.info(f"{device.name} ({device.owner}) has {event_type}")

    # --- API Helper Methods ---

    def get_devices(self):
        """Get all registered devices with their current status"""
        with self.app.app_context():
            devices = Device.query.all()
            return [d.to_dict() for d in devices]

    def add_device(self, mac_address, name, owner=None):
        """
        Register a new device to monitor.
        
        Args:
            mac_address (str): MAC address in format AA:BB:CC:DD:EE:FF
            name (str): Device name (e.g., "Jared's iPhone")
            owner (str): Owner name (e.g., "Jared")
            
        Returns:
            tuple: (success: bool, message: str)
        """
        with self.app.app_context():
            try:
                # Check if device already exists
                existing = Device.query.filter_by(mac_address=mac_address).first()
                if existing:
                    return False, "Device with this MAC address already exists"
                
                # Create new device
                device = Device(
                    mac_address=mac_address.upper(),
                    name=name,
                    owner=owner,
                    is_home=False
                )
                
                db.session.add(device)
                db.session.commit()
                
                logger.info(f"Added new device: {name} ({mac_address})")
                return True, "Device added successfully"
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding device: {e}")
                return False, str(e)

    def remove_device(self, device_id):
        """
        Remove a device from monitoring.
        
        Args:
            device_id (int): Device ID to remove
            
        Returns:
            tuple: (success: bool, message: str)
        """
        with self.app.app_context():
            try:
                device = Device.query.get(device_id)
                if not device:
                    return False, "Device not found"
                
                db.session.delete(device)
                db.session.commit()
                
                logger.info(f"Removed device: {device.name}")
                return True, "Device removed successfully"
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error removing device: {e}")
                return False, str(e)

    def update_device(self, device_id, name=None, owner=None):
        """
        Update device information.
        
        Args:
            device_id (int): Device ID to update
            name (str, optional): New name
            owner (str, optional): New owner
            
        Returns:
            tuple: (success: bool, message: str)
        """
        with self.app.app_context():
            try:
                device = Device.query.get(device_id)
                if not device:
                    return False, "Device not found"
                
                if name:
                    device.name = name
                if owner:
                    device.owner = owner
                
                db.session.commit()
                
                logger.info(f"Updated device: {device.name}")
                return True, "Device updated successfully"
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating device: {e}")
                return False, str(e)

    def get_presence_history(self, hours=24):
        """
        Get presence events for the last N hours.
        
        Args:
            hours (int): Number of hours to look back
            
        Returns:
            list: List of presence event dictionaries
        """
        with self.app.app_context():
            cutoff = datetime.now() - timedelta(hours=hours)
            events = (
                PresenceEvent.query
                .filter(PresenceEvent.timestamp >= cutoff)
                .order_by(PresenceEvent.timestamp.desc())
                .all()
            )
            return [e.to_dict() for e in events]

    def get_status(self):
        """Get current monitoring status"""
        with self._lock:
            return {
                'monitoring': self.monitoring,
                'target_ip': self.target_ip,
                'scan_interval': self.scan_interval,
                'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None
            }

    def cleanup(self):
        """Stop monitoring thread"""
        logger.info("Stopping PresenceMonitor...")
        self.monitoring = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)