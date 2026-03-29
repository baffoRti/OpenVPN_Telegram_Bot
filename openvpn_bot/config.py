import os
import logging
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

logger = logging.getLogger(__name__)

class Config:
    # === Required settings ===
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []
    
    # === OpenVPN paths (auto-detected if not set) ===
    # Main OpenVPN directory - leave empty for auto-detection
    # Auto-detection: /etc/openvpn/server → /etc/openvpn
    OPENVPN_SERVER_DIR = os.getenv('OPENVPN_SERVER_DIR', '')
    
    # Individual path overrides (derived from OPENVPN_SERVER_DIR if not set)
    OPENVPN_SERVER_CONF = os.getenv('OPENVPN_SERVER_CONF', '')
    OPENVPN_EASYRSA_DIR = os.getenv('OPENVPN_EASYRSA_DIR', '')
    OPENVPN_TLS_CRYPT_KEY = os.getenv('OPENVPN_TLS_CRYPT_KEY', '')
    OPENVPN_TLS_AUTH_KEY = os.getenv('OPENVPN_TLS_AUTH_KEY', '')
    OPENVPN_CRL_PEM = os.getenv('OPENVPN_CRL_PEM', '')
    OPENVPN_IPP_TXT = os.getenv('OPENVPN_IPP_TXT', '')
    OPENVPN_CLIENT_TEMPLATE = os.getenv('OPENVPN_CLIENT_TEMPLATE', '')
    
    # Server settings for client config generation
    OPENVPN_SERVER_IP = os.getenv('OPENVPN_SERVER_IP', '')
    OPENVPN_SERVER_PORT = os.getenv('OPENVPN_SERVER_PORT', '1194')
    OPENVPN_SERVER_PROTO = os.getenv('OPENVPN_SERVER_PROTO', '')
    
    # === Other settings ===
    OPENVPN_DB_PATH = os.getenv('OPENVPN_DB_PATH', 'openvpn_stats.db')
    CERT_SCRIPT_PATH = os.getenv('CERT_SCRIPT_PATH', './manage_certs.sh')
    OPENVPN_CERT_DIR = os.getenv('OPENVPN_CERT_DIR', '')
    OPENVPN_STATUS_FILE = os.getenv('OPENVPN_STATUS_FILE', '/var/log/openvpn/status.log')
    OPENVPN_MANAGEMENT_HOST = os.getenv('OPENVPN_MANAGEMENT_HOST', 'localhost')
    OPENVPN_MANAGEMENT_PORT = os.getenv('OPENVPN_MANAGEMENT_PORT', '7505')
    
    # === Traffic notifications ===
    TRAFFIC_THRESHOLDS = list(map(int, os.getenv('TRAFFIC_THRESHOLDS', '500,700,900').split(',')))
    TRAFFIC_CHECK_INTERVAL = int(os.getenv('TRAFFIC_CHECK_INTERVAL', '10800'))
    
    # === Internal flags (set during validation) ===
    TRAFFIC_MONITOR_AVAILABLE = False
    
    # === Hardcoded settings ===
    TRAFFIC_MONITOR_REPO = 'https://github.com/baffoRti/OpenVPN_Traffic_Monitor'

    @staticmethod
    def validate():
        if not Config.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN environment variable is not set")
        if not Config.ADMIN_IDS:
            raise ValueError("ADMIN_IDS environment variable is not set or empty")
        if not os.path.exists(Config.CERT_SCRIPT_PATH):
            raise ValueError(f"CERT_SCRIPT_PATH does not exist: {Config.CERT_SCRIPT_PATH}")
        
        # Auto-detect and configure OpenVPN paths
        Config._detect_openvpn_paths()
        
        # Check if traffic monitor database exists
        if os.path.exists(Config.OPENVPN_DB_PATH):
            Config.TRAFFIC_MONITOR_AVAILABLE = True
            logger.info(f"Traffic monitor database found at: {Config.OPENVPN_DB_PATH}")
        else:
            Config.TRAFFIC_MONITOR_AVAILABLE = False
            logger.warning(
                f"Traffic monitor database not found at: {Config.OPENVPN_DB_PATH}. "
                f"Traffic-related features will be disabled."
            )
        
        # Validate traffic check interval
        if Config.TRAFFIC_CHECK_INTERVAL < 60:
            logger.warning(
                f"TRAFFIC_CHECK_INTERVAL ({Config.TRAFFIC_CHECK_INTERVAL}s) is too low. "
                f"Setting to minimum of 60 seconds."
            )
            Config.TRAFFIC_CHECK_INTERVAL = 60
    
    @staticmethod
    def _detect_openvpn_paths():
        """Auto-detect OpenVPN configuration paths if not explicitly set."""
        # Detect OpenVPN server directory
        if not Config.OPENVPN_SERVER_DIR:
            if os.path.exists('/etc/openvpn/server/server.conf'):
                Config.OPENVPN_SERVER_DIR = '/etc/openvpn/server'
                logger.info(f"Auto-detected OpenVPN dir: {Config.OPENVPN_SERVER_DIR}")
            elif os.path.exists('/etc/openvpn/server.conf'):
                Config.OPENVPN_SERVER_DIR = '/etc/openvpn'
                logger.info(f"Auto-detected OpenVPN dir: {Config.OPENVPN_SERVER_DIR}")
            else:
                logger.warning(
                    "Cannot auto-detect OpenVPN directory. "
                    "Set OPENVPN_SERVER_DIR environment variable."
                )
                return
        
        # Derive paths from OPENVPN_SERVER_DIR if not set
        if Config.OPENVPN_SERVER_DIR:
            if not Config.OPENVPN_SERVER_CONF:
                Config.OPENVPN_SERVER_CONF = os.path.join(Config.OPENVPN_SERVER_DIR, 'server.conf')
            
            if not Config.OPENVPN_EASYRSA_DIR:
                Config.OPENVPN_EASYRSA_DIR = os.path.join(Config.OPENVPN_SERVER_DIR, 'easy-rsa')
            
            if not Config.OPENVPN_TLS_CRYPT_KEY:
                Config.OPENVPN_TLS_CRYPT_KEY = os.path.join(Config.OPENVPN_SERVER_DIR, 'tls-crypt.key')
            
            if not Config.OPENVPN_TLS_AUTH_KEY:
                Config.OPENVPN_TLS_AUTH_KEY = os.path.join(Config.OPENVPN_SERVER_DIR, 'tls-auth.key')
            
            if not Config.OPENVPN_CRL_PEM:
                Config.OPENVPN_CRL_PEM = os.path.join(Config.OPENVPN_SERVER_DIR, 'crl.pem')
            
            if not Config.OPENVPN_IPP_TXT:
                Config.OPENVPN_IPP_TXT = os.path.join(Config.OPENVPN_SERVER_DIR, 'ipp.txt')
            
            # Client template (optional - will be generated if not found)
            if not Config.OPENVPN_CLIENT_TEMPLATE:
                for tpl in ['client-template.txt', 'client-common.txt']:
                    tpl_path = os.path.join(Config.OPENVPN_SERVER_DIR, tpl)
                    if os.path.exists(tpl_path):
                        Config.OPENVPN_CLIENT_TEMPLATE = tpl_path
                        break
            
            # Output directory for .ovpn files
            if not Config.OPENVPN_CERT_DIR:
                Config.OPENVPN_CERT_DIR = os.path.join(Config.OPENVPN_EASYRSA_DIR, 'pki')
        
        logger.info(f"OpenVPN config: server_conf={Config.OPENVPN_SERVER_CONF}")
    
    @staticmethod
    def get_traffic_monitor_help_message() -> str:
        """Return help message when traffic monitor is not available."""
        return (
            "⚠️ OpenVPN Traffic Monitor is not installed\n\n"
            "Traffic statistics features are unavailable because the database path "
            "is not set or the application is not installed.\n\n"
            f"To install, visit: {Config.TRAFFIC_MONITOR_REPO}\n\n"
            "Make sure the OPENVPN_DB_PATH variable points to an existing database."
        )
