# app/main.py
from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from .winrm_utils import shutdown_via_winrm

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
from .winrm_utils import get_winrm_info

from .database import Base, engine, get_db
from . import crud, schemas
from .scheduler import start_scheduler, scan_network
from .config import settings

from datetime import datetime

# Tworzenie tabel
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PC Manager")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.post("/computers/{computer_id}/shutdown_manual")
def shutdown_manual(
    computer_id: int,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Ręczne wyłączenie komputera przez WinRM.
    Wymaga podania hasła ADMIN_TOGGLE_PASSWORD z .env.
    """
    # Sprawdzenie hasła admina
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

@app.get("/scan-now")
def scan_now():
    """
    Ręczne odpalenie skanowania sieci.
    Niczego nie wyłącza, tylko szuka komputerów po WinRM.
    """
    scan_network()
    return {"status": "ok", "message": "Scan finished"}

@app.post("/computers/{computer_id}/set_status")
def set_status(
    computer_id: int,
    status: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Zmiana statusu komputera:
      - found     -> 'Znaleziony'
      - managed   -> 'Zarządzany'
      - exception -> 'Wyjątek'
    Zabezpieczona hasłem ADMIN_TOGGLE_PASSWORD z .env
    """
    if password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Niepoprawne haslo")

    comp = crud.get_computer(db, computer_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Computer not found")

    if status not in ["found", "managed", "exception"]:
        raise HTTPException(status_code=400, detail="Niepoprawny status")

    update = schemas.ComputerUpdate(status=status)
    crud.update_computer(db, comp, update)

    return RedirectResponse("/", status_code=303)


@app.on_event("startup")
async def on_startup():
    start_scheduler()


@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    computers = crud.get_all_computers(db)
    unapproved = crud.get_unapproved_computers(db)
    logs = crud.get_recent_shutdown_logs(db, limit=20)
    today = date.today()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "computers": computers,
            "unapproved": unapproved,
            "logs": logs,
            "today": today,
        },
    )


@app.post("/computers/{computer_id}/exclude_today")
def exclude_today(
    computer_id: int,
    user_label: str = Form("unknown"),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
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
