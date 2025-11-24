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
      - current_user: zalogowany użytkownik (DOMENA\\user albo PC\\user)
      - error_message: opis błędu, jeśli wystąpił
    """
    try:
        session = winrm.Session(
            f"http://{ip}:5985/wsman",
            auth=(WINRM_USER, WINRM_PASSWORD),
            transport="ntlm",
        )

        ps_script = r"""
        $cs = Get-CimInstance -ClassName Win32_ComputerSystem
        $name = $cs.Name
        $user = $cs.UserName
        "$name|$user"
        """

        result = session.run_ps(ps_script)

        if result.status_code != 0:
            err = result.std_err.decode(errors="ignore") or "WinRM error"
            return False, None, None, err

        out = result.std_out.decode(errors="ignore").strip()
        if "|" in out:
            hostname, user = out.split("|", 1)
        else:
            hostname, user = out, None

        hostname = hostname.strip() or None
        user = user.strip() or None

        return True, hostname, user, None

    except Exception as e:
        return False, None, None, str(e)


def shutdown_via_winrm(ip: str) -> Tuple[bool, str]:
    """
    Wyłącza komputer przez WinRM.
    """
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
