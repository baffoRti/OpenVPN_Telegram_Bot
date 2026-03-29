import socket
import logging
import os
from datetime import datetime

from openvpn_bot.config import Config
from openvpn_bot.utils import validate_username

logger = logging.getLogger(__name__)

# Known header lines in status-version 1 that are NOT client data
_SKIP_HEADERS = {
    'OpenVPN CLIENT LIST',
    'Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since',
    'ROUTING TABLE',
    'GLOBAL STATS',
    'END',
}


def _format_relative(dt_str: str) -> str:
    """Format a datetime string as relative time (e.g. '2h 15m ago')."""
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        delta = datetime.now() - dt
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return dt_str
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m ago"
        elif minutes > 0:
            return f"{minutes}m {seconds}s ago"
        else:
            return f"{seconds}s ago"
    except (ValueError, TypeError):
        return dt_str


def get_connected_clients():
    """
    Get currently connected OpenVPN clients by parsing the status file.
    Supports status-version 1 format (used by openvpn-install.sh):
        Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
    """
    status_file = Config.OPENVPN_STATUS_FILE
    if not os.path.exists(status_file):
        logger.warning(f"OpenVPN status file not found at {status_file}")
        return []

    try:
        clients = []
        with open(status_file, 'r') as f:
            lines = f.readlines()

        logger.info(f"Status file: {status_file}, {len(lines)} lines")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip known header/section lines
            if line in _SKIP_HEADERS:
                continue
            # Skip "Updated,..." line
            if line.startswith('Updated,'):
                continue
            # Skip lines that don't look like CSV data (must have commas)
            if ',' not in line:
                continue

            parts = line.split(',')

            # Routing table line: Virtual Address,Common Name,Real Address,Last Ref
            # Has 4 fields and first field looks like an IP (10.8.x.x)
            if len(parts) == 4 and parts[0].startswith('10.'):
                continue

            # Client line (status-version 1): Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
            if len(parts) >= 5:
                common_name = parts[0]
                real_address = parts[1]
                try:
                    bytes_received = int(parts[2])
                except ValueError:
                    bytes_received = 0
                try:
                    bytes_sent = int(parts[3])
                except ValueError:
                    bytes_sent = 0
                connected_since_raw = parts[4]
                clients.append({
                    'common_name': common_name,
                    'real_address': real_address,
                    'virtual_address': '',  # not in status-version 1 client lines
                    'bytes_received': bytes_received,
                    'bytes_sent': bytes_sent,
                    'connected_since': connected_since_raw,
                    'connected_since_display': _format_relative(connected_since_raw),
                })

        logger.info(f"Found {len(clients)} connected clients")
        return clients
    except Exception as e:
        logger.error(f"Error reading OpenVPN status file {status_file}: {e}")
        return []


def disconnect_client(username):
    """
    Disconnect a specific OpenVPN client via the management interface.
    Uses a raw TCP socket instead of telnet for reliability.
    Management host/port are configured via OPENVPN_MANAGEMENT_* in .env.
    """
    management_host = Config.OPENVPN_MANAGEMENT_HOST
    management_port = int(Config.OPENVPN_MANAGEMENT_PORT)

    if not validate_username(username):
        logger.error(f"Invalid username for disconnection: {username}")
        return False, f"Invalid username: {username}"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((management_host, management_port))

        # Read the welcome banner
        banner = sock.recv(4096).decode('utf-8', errors='replace')
        logger.info(f"Management banner: {banner.strip()}")

        # Send kill command
        cmd = f"kill {username}\n"
        sock.sendall(cmd.encode('utf-8'))

        # Read response (may come in multiple chunks)
        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                # Stop when we see SUCCESS or ERROR
                text = response.decode('utf-8', errors='replace')
                if 'SUCCESS:' in text or 'ERROR:' in text:
                    break
            except socket.timeout:
                break

        sock.close()
        response_text = response.decode('utf-8', errors='replace')
        logger.info(f"Management response for kill {username}: {response_text.strip()}")

        if 'SUCCESS:' in response_text:
            return True, f"Client {username} disconnected successfully"
        elif 'ERROR:' in response_text:
            # Extract error message
            for line in response_text.splitlines():
                if 'ERROR:' in line:
                    return False, line.strip()
            return False, f"Failed to disconnect {username}"
        else:
            return False, f"Unexpected response: {response_text.strip()[:200]}"

    except socket.timeout:
        logger.error(f"Timeout connecting to management interface for {username}")
        return False, "Timeout: management interface did not respond"
    except ConnectionRefusedError:
        logger.error(f"Connection refused to {management_host}:{management_port}")
        return False, f"Management interface not available at {management_host}:{management_port}. Is it enabled in server.conf?"
    except Exception as e:
        logger.error(f"Error disconnecting {username}: {e}")
        return False, f"Error: {str(e)}"


def get_client_traffic_from_db(username):
    """
    Get traffic statistics for a specific client from the database.
    Delegates to traffic_monitor for DB operations.
    """
    from . import traffic_monitor
    return traffic_monitor.get_user_traffic(username)
