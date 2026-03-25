import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Config:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []
    OPENVPN_DB_PATH = os.getenv('OPENVPN_DB_PATH', 'openvpn_stats.db')
    CERT_SCRIPT_PATH = os.getenv('CERT_SCRIPT_PATH', './manage_certs.sh')
    OPENVPN_CERT_DIR = os.getenv('OPENVPN_CERT_DIR', '/etc/openvpn/easy-rsa/pki')
    OPENVPN_STATUS_FILE = os.getenv('OPENVPN_STATUS_FILE', '/var/log/openvpn/status.log')
    OPENVPN_MANAGEMENT_HOST = os.getenv('OPENVPN_MANAGEMENT_HOST', 'localhost')
    OPENVPN_MANAGEMENT_PORT = os.getenv('OPENVPN_MANAGEMENT_PORT', '7505')
    # Traffic thresholds in GB for notifications
    TRAFFIC_THRESHOLDS = list(map(int, os.getenv('TRAFFIC_THRESHOLDS', '500,700,900').split(',')))

    @staticmethod
    def validate():
        if not Config.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN environment variable is not set")
        if not Config.ADMIN_IDS:
            raise ValueError("ADMIN_IDS environment variable is not set or empty")
        if not os.path.exists(Config.OPENVPN_DB_PATH):
            raise ValueError(f"OPENVPN_DB_PATH does not exist: {Config.OPENVPN_DB_PATH}")
        if not os.path.exists(Config.CERT_SCRIPT_PATH):
            raise ValueError(f"CERT_SCRIPT_PATH does not exist: {Config.CERT_SCRIPT_PATH}")
        # Additional validations can be added here
