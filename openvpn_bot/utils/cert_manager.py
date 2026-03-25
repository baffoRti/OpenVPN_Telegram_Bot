import subprocess
import logging
from openvpn_bot.config import Config

logger = logging.getLogger(__name__)

def run_cert_script(operation, *args):
    """
    Run the certificate management script with the given operation and arguments.
    The script path is configurable via Config.CERT_SCRIPT_PATH.
    """
    script_path = Config.CERT_SCRIPT_PATH
    if not script_path:
        logger.error("Certificate script path is not configured")
        return False, "Certificate script path is not configured"
    
    # Build the command: script_path operation arg1 arg2 ...
    cmd = [script_path, operation] + list(args)
    
    try:
        result = subprocess.run(cmd, check=True, 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Certificate script failed: {e.stderr}")
        return False, e.stderr
    except FileNotFoundError:
        logger.error(f"Certificate script not found at {script_path}")
        return False, f"Certificate script not found at {script_path}"
    except Exception as e:
        logger.error(f"Unexpected error running certificate script: {e}")
        return False, f"Unexpected error: {str(e)}"

def revoke_certificate(common_name):
    """Revoke a certificate for the given common name."""
    return run_cert_script('revoke', common_name)

def generate_certificate(common_name):
    """Generate a certificate for the given common name."""
    return run_cert_script('generate', common_name)

def renew_certificate(common_name):
    """Renew a certificate for the given common name."""
    return run_cert_script('renew', common_name)

def list_certificates():
    """List all certificates."""
    return run_cert_script('list')
