# app/main.py
import socket
from datetime import date, time  # <- upewnij się, że jest też `time`

import subprocess
import platform

from datetime import datetime, date
from pathlib import Path
from typing import List

from fastapi import (
    FastAPI,
    Request,
    Depends,
    Form,
    HTTPException,
)
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import crud, schemas, models
from .config import settings
from .winrm_utils import shutdown_via_winrm, get_winrm_info
from .scheduler import start_scheduler, scan_network

# --- Inicjalizacja bazy ---
Base.metadata.create_all(bind=engine)

# --- FastAPI + szablony + statyczne ---
app = FastAPI()

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
# Stała informacyjna do wyświetlania w UI
NIGHTLY_SHUTDOWN_HOUR = time(22, 0)  # 22:00

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def ping_host(target: str, timeout: int = 1) -> bool:
    """
    Prosty ping IP/hosta. Zwraca True jeśli host odpowiada, False jeśli nie.
    """
    if not target:
        return False

    param = "-n" if platform.system().lower().startswith("win") else "-c"
    cmd = ["ping", param, "1", target]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return result.returncode == 0
    except Exception:
        return False

@app.post("/check-online")
def check_online(db: Session = Depends(get_db)):
    """
    Szybkie sprawdzanie statusu online przez ping dla wszystkich komputerów.
    Bez hasła admina, bo to tylko odczyt / diagnostyka.
    """
    computers = crud.get_all_computers(db)
    result = {}

    for c in computers:
        if c.ip:
            is_online = ping_host(c.ip)
            result[c.id] = "online" if is_online else "offline"
        else:
            result[c.id] = "unknown"

    # FastAPI samo zwróci JSON
    return {"online": result}

def ping_host(ip: str, timeout: float = 1.0) -> bool:
    """
    Prosty ping – 1 pakiet, mały timeout.
    Nie zapisujemy nic w bazie, tylko sprawdzamy online/offline.
    """
    system = platform.system().lower()
    if system == "windows":
        # Windows: -n liczba pakietów, -w timeout w ms
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
    else:
        # Linux: -c liczba pakietów, -W timeout w sekundach
        cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]

    try:
        return subprocess.call(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0
    except Exception:
        return False

def is_online(ip: str, timeout: float = 0.2) -> bool:
    """
    Szybkie sprawdzenie, czy host odpowiada na porcie 5985 (WinRM).
    Nic nie zapisuje do bazy – tylko zwraca True/False.
    """
    if not ip:
        return False
    try:
        with socket.create_connection((ip, 5985), timeout=timeout):
            return True
    except OSError:
        return False


# --- Endpoint: ręczne wyłączenie jednego komputera ---
@app.post("/computers/{computer_id}/shutdown_manual")
def shutdown_manual(
    computer_id: int,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Ręczne wyłączenie jednego komputera po WinRM.
    Wymaga hasła ADMIN_TOGGLE_PASSWORD.
    """
    if password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Niepoprawne haslo")

    comp = crud.get_computer(db, computer_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Computer not found")

    success, msg = shutdown_via_winrm(comp.ip)
    status = "manual_success" if success else "manual_failed"

    now = datetime.utcnow()
    crud.create_shutdown_log(
        db,
        computer_id=comp.id,
        scheduled_for=now,
        executed_at=now,
        status=status,
        message=msg,
    )

    return RedirectResponse("/", status_code=303)


# --- Debug WinRM dla jednego IP ---
@app.get("/debug-winrm/{ip}")
def debug_winrm(ip: str):
    """
    Diagnostyka WinRM dla konkretnego IP.
    Pokazuje, czy logowanie działa, jaki hostname i user zwraca, lub jaki jest błąd.
    """
    success, hostname, user, err = get_winrm_info(ip)
    return {
        "ip": ip,
        "success": success,
        "hostname": hostname,
        "user": user,
        "error": err,
    }


# --- Ręczne skanowanie sieci ---
@app.post("/scan-now")
def scan_now(admin_password: str = Form(...), db: Session = Depends(get_db)):
    if admin_password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password")
    scan_network()   # lub wywołanie funkcji ze scheduler.py
    return RedirectResponse("/", status_code=303)



# --- Zmiana statusu komputera (managed / exception) ---
@app.post("/computers/{computer_id}/set_status")
def set_status(
    computer_id: int,
    status: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Zmiana statusu komputera:
    - managed   -> zarządzany, będzie wyłączany o 22:00
    - exception -> wyjątek, nigdy nie wyłączamy automatycznie
    (status 'found' zostaje tylko z auto-skanu)
    """
    if password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Niepoprawne haslo")

    if status not in ["managed", "exception"]:
        raise HTTPException(status_code=400, detail="Niepoprawny status")

    comp = crud.get_computer(db, computer_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Computer not found")

    update = schemas.ComputerUpdate(status=status)
    crud.update_computer(db, comp, update)

    return RedirectResponse("/", status_code=303)

@app.post("/computers/{computer_id}/exclude_today")
def computer_exclude_today(
    computer_id: int,
    user: str = Form(...),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    # Wymagane hasło admina
    if settings.ADMIN_TOGGLE_PASSWORD and password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Nieprawidłowe hasło administratora.")

    computer = crud.get_computer(db, computer_id)
    if not computer:
        raise HTTPException(status_code=404, detail="Komputer nie znaleziony.")

    # Zapisujemy jednodniowy wyjątek – w reason trzymamy np. "Jan Kowalski"
    crud.add_exclusion(db, computer_id=computer_id, exclusion_date=date.today(), reason=user)

    return RedirectResponse(url="/", status_code=303)


# --- Startup: scheduler ---
@app.on_event("startup")
async def on_startup():
    # Uwaga: w trybie --reload zobaczysz ten log dwukrotnie (to normalne),
    # w produkcji (bez reload) tylko raz.
    start_scheduler()


# --- Strona główna GUI ---
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    computers = crud.get_all_computers(db)

    # czy admin password ustawione
    admin_password_set = bool(settings.ADMIN_TOGGLE_PASSWORD)

    today = date.today()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "computers": computers,
            "admin_password_set": admin_password_set,
            "today": today,
            "shutdown_hour": NIGHTLY_SHUTDOWN_HOUR,
        },
    )




# --- Endpoint: "Nie wyłączaj dziś" ---
@app.post("/computers/{computer_id}/exclude_today")
def exclude_today(
    computer_id: int,
    user_label: str = Form("unknown"),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    """
    Zapisuje w bazie, że dany komputer ma być pominięty przy
    dzisiejszym nocnym wyłączaniu.
    """
    comp = crud.get_computer(db, computer_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Computer not found")

    data = schemas.DailyExclusionCreate(
        computer_id=comp.id,
        date_for=date.today(),
        user_label=user_label,
        reason=reason or None,
    )
    crud.create_daily_exclusion(db, data)
    return RedirectResponse("/", status_code=303)
