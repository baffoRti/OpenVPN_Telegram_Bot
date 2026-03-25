import subprocess
import platform
import logging

logger = logging.getLogger(__name__)

def run_command(command):
    """Run a shell command and return (success, output_or_error)."""
    try:
        result = subprocess.run(command, shell=True, check=True, 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command '{command}' failed with error: {e.stderr}")
        return False, e.stderr.strip()
    except Exception as e:
        logger.error(f"Unexpected error running command '{command}': {e}")
        return False, f"Unexpected error: {str(e)}"

def get_service_status(service_name="openvpn"):
    """Get the status of a service. Returns (success: bool, status_or_error: str)."""
    if platform.system() == "Windows":
        return False, "Windows service status check not implemented"

    import subprocess
    try:
        result = subprocess.run(
            f"systemctl is-active {service_name}",
            shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = result.stdout.strip()
        if result.returncode == 0:
            return True, output  # "active"
        else:
            # inactive, failed, activating, etc.
            return False, output if output else (result.stderr.strip() or "unknown")
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def start_service(service_name="openvpn"):
    """Start a service."""
    if platform.system() == "Windows":
        return False, "Windows service start not implemented"
    else:
        success, output = run_command(f"systemctl start {service_name}")
        return success, output

def stop_service(service_name="openvpn"):
    """Stop a service."""
    if platform.system() == "Windows":
        return False, "Windows service stop not implemented"
    else:
        success, output = run_command(f"systemctl stop {service_name}")
        return success, output

def restart_service(service_name="openvpn"):
    """Restart a service."""
    if platform.system() == "Windows":
        return False, "Windows service restart not implemented"
    else:
        success, output = run_command(f"systemctl restart {service_name}")
        return success, output
