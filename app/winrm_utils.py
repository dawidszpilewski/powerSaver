# app/winrm_utils.py
from typing import Tuple, Optional
import winrm

from .config import settings

WINRM_USER = settings.WINRM_USER
WINRM_PASSWORD = settings.WINRM_PASSWORD


def get_winrm_info(ip: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Pobiera informacje przez WinRM:
      - success: czy połączenie udane
      - hostname: nazwa komputera (np. NAZWA-PC)
      - user: zalogowany użytkownik (np. DOMENA\\uzytkownik)
      - error: treść błędu (jeśli success=False)
    """
    if not WINRM_USER or not WINRM_PASSWORD:
        return False, None, None, "Brak konfiguracji WINRM_USER/WINRM_PASSWORD"

    try:
        session = winrm.Session(
            f"http://{ip}:5985/wsman",
            auth=(WINRM_USER, WINRM_PASSWORD),
            transport="ntlm",
        )

        # Hostname
        r_host = session.run_cmd("hostname")
        if r_host.status_code != 0:
            return False, None, None, r_host.std_err.decode(errors="ignore") or "hostname cmd failed"
        hostname = r_host.std_out.decode(errors="ignore").strip()

        # Zalogowany użytkownik
        r_user = session.run_cmd("whoami")
        if r_user.status_code != 0:
            return False, hostname, None, r_user.std_err.decode(errors="ignore") or "whoami cmd failed"
        user = r_user.std_out.decode(errors="ignore").strip()

        return True, hostname, user, None

    except Exception as e:
        return False, None, None, str(e)


def shutdown_via_winrm(ip: str) -> Tuple[bool, str]:
    """
    Wyłącza komputer po WinRM.
    Zwraca (success, message).
    """
    if not WINRM_USER or not WINRM_PASSWORD:
        return False, "Brak konfiguracji WINRM_USER/WINRM_PASSWORD"

    try:
        session = winrm.Session(
            f"http://{ip}:5985/wsman",
            auth=(WINRM_USER, WINRM_PASSWORD),
            transport="ntlm",
        )
        result = session.run_cmd("shutdown", ["/s", "/f", "/t", "0"])

        if result.status_code == 0:
            msg = result.std_out.decode(errors="ignore") or "Shutdown OK"
            return True, msg
        else:
            msg = result.std_err.decode(errors="ignore") or "Shutdown failed"
            return False, msg

    except Exception as e:
        return False, str(e)
