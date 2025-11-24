from pathlib import Path
from typing import List

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import settings
from . import models, crud
from .database import engine, get_db
from .scheduler import start_scheduler, scan_network
from .winrm_utils import shutdown_via_winrm

# --- ŚCIEŻKI DO SZABLONÓW I STATYCZNYCH ---
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# --- INICJALIZACJA BAZY ---
models.Base.metadata.create_all(bind=engine)

# --- APLIKACJA FASTAPI ---
app = FastAPI()

# Statyczne pliki: /static/...
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Szablony Jinja2
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# --- START SCHEDULERA ---
@app.on_event("startup")
async def on_startup() -> None:
    # Uwaga: przy `--reload` w dev log może pojawić się dwa razy,
    # w produkcji (bez reload) scheduler startuje tylko raz.
    print("[scheduler] APScheduler wystartował (scan + nightly shutdown).")
    start_scheduler()


# --- STRONA GŁÓWNA ---
@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    """
    Strona główna z listą komputerów.
    - status 'Znaleziony' -> tabela "Komputery znalezione w sieci"
    - inne statusy ('Zarządzany', 'Wyjątek', puste) -> tabela "Komputery zarządzane / wyjątki"
    """
    computers: List[models.Computer] = crud.get_all_computers(db)
    shutdown_logs = crud.get_recent_shutdown_logs(db, limit=50)

    found = [c for c in computers if c.status == "Znaleziony"]
    managed_unfound = [c for c in computers if c.status != "Znaleziony"]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "found": found,
            "managed_unfound": managed_unfound,
            "shutdown_logs": shutdown_logs,
        },
    )


# --- RĘCZNE SKANOWANIE SIECI (NA HASŁO) ---
@app.post("/scan-now")
def scan_now(admin_password: str = Form(...)):
    if admin_password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Nieprawidłowe hasło do skanowania")
    print("[scan-now] Ręczne skanowanie sieci...")
    scan_network()
    return RedirectResponse(url="/", status_code=303)


# --- ZMIANA STATUSU (NA HASŁO) ---
@app.post("/computers/{computer_id}/set_status")
def set_status(
    computer_id: int,
    status: str = Form(...),
    admin_password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Zmiana statusu komputera:
    - 'Znaleziony' jest tylko z automatu po skanowaniu.
    - z GUI można ustawić tylko 'Zarządzany' lub 'Wyjątek'.
    """
    if admin_password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Nieprawidłowe hasło do zmiany statusu")

    if status not in ("Zarządzany", "Wyjątek"):
        raise HTTPException(status_code=400, detail="Niedozwolony status (tylko Zarządzany/Wyjątek)")

    computer = db.query(models.Computer).filter(models.Computer.id == computer_id).first()
    if not computer:
        raise HTTPException(status_code=404, detail="Komputer nie istnieje")

    computer.status = status
    db.add(computer)
    db.commit()

    return RedirectResponse(url="/", status_code=303)


# --- RĘCZNE WYŁĄCZENIE (NA HASŁO) ---
@app.post("/computers/{computer_id}/shutdown_manual")
def shutdown_manual(
    computer_id: int,
    admin_password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Ręczne wyłączenie jednego komputera przez WinRM po wpisaniu hasła.
    """
    if admin_password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Nieprawidłowe hasło do wyłączenia")

    computer = db.query(models.Computer).filter(models.Computer.id == computer_id).first()
    if not computer:
        raise HTTPException(status_code=404, detail="Komputer nie istnieje")

    if not computer.ip:
        raise HTTPException(status_code=400, detail="Brak adresu IP komputera")

    ok, msg = shutdown_via_winrm(computer.ip)

    # Zapis do logów wyłączeń
    from datetime import datetime

    db_log = models.ShutdownLog(
        computer_id=computer.id,
        ip=computer.ip,
        status="OK" if ok else "ERROR",
        message=msg,
        executed_at=datetime.now(),
    )
    db.add(db_log)
    db.commit()

    if not ok:
        raise HTTPException(status_code=500, detail=f"Wyłączanie nie powiodło się: {msg}")

    return RedirectResponse(url="/", status_code=303)
