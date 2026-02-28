"""Windows networking utilities — LAN IP detection and firewall check."""

import socket
import subprocess
import logging

logger = logging.getLogger("mtcs.networking")


def get_local_ip() -> str:
    """Detect the machine's LAN IPv4 address using a UDP socket trick."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Doesn't actually send data — just forces OS to pick the right interface
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        logger.warning("Could not detect LAN IP, falling back to 127.0.0.1")
        return "127.0.0.1"


def check_firewall(port: int) -> dict:
    """
    Check if Windows Firewall allows inbound TCP on the given port.
    Returns a dict with 'allowed' (bool) and 'message' (str).
    """
    result = {"allowed": False, "message": "", "checked": False}

    try:
        # Use netsh — much faster than PowerShell Get-NetFirewallRule pipeline
        cmd = f'netsh advfirewall firewall show rule name=all dir=in protocol=tcp localport={port}'
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, shell=True
        )
        result["checked"] = True

        if proc.returncode == 0 and "Allow" in proc.stdout:
            result["allowed"] = True
            result["message"] = f"Port {port}/TCP is allowed through Windows Firewall."
        else:
            result["allowed"] = False
            result["message"] = (
                f"Port {port}/TCP may be blocked by Windows Firewall. "
                f"To allow LAN access, run in an elevated PowerShell:\n"
                f'  New-NetFirewallRule -DisplayName "MTCS Trading" '
                f"-Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow"
            )
    except subprocess.TimeoutExpired:
        result["message"] = "Firewall check timed out. LAN access may not work."
        logger.warning("Firewall check timed out")
    except Exception as e:
        result["message"] = f"Could not check firewall: {e}"
        logger.warning(f"Firewall check failed: {e}")

    return result


def get_network_info(port: int) -> dict:
    """Get complete network info for display in UI."""
    local_ip = get_local_ip()
    firewall = check_firewall(port)

    return {
        "local_ip": local_ip,
        "port": port,
        "access_url": f"http://{local_ip}:{port}",
        "firewall": firewall,
    }
