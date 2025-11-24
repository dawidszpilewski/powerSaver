from pathlib import Path
from datetime import date, datetime

from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import crud, schemas
from .scheduler import start_scheduler, scan_network
from .config import settings
from .winrm_utils import shutdown_via_winrm, get_winrm_info


# --- Inicjalizacja bazy ---
Base.metadata.create_all(bind=engine)

# --- Aplikacja FastAPI ---
app = FastAPI()

# Ścieżki oparte na położeniu pliku main.py
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Statyczne pliki (favicon, logo, custom.js, itp.)
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

# Szablony Jinja2
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# --- Start schedulerów przy starcie aplikacji ---
@app.on_event("startup")
async def on_startup():
    # Harmonogram: skan + nocne wyłączanie
    start_scheduler()


# --- Endpoint: ręczne wyłączenie komputera ---
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


# --- Endpoint: debug WinRM dla jednego IP ---
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


# --- Endpoint: ręczne skanowanie sieci ---
@app.post("/scan-now")
def scan_now(password: str = Form(...)):
    """
    Ręczne wyzwolenie skanowania sieci.
    Wymaga hasła ADMIN_TOGGLE_PASSWORD.
    """
    if password != settings.ADMIN_TOGGLE_PASSWORD:
        raise HTTPException(status_code=403, detail="Niepoprawne haslo")

    scan_network()
    return RedirectResponse("/", status_code=303)


# --- Endpoint: zmiana statusu komputera (managed / exception) ---
@app.post("/computers/{computer_id}/set_status")
def set_status(
    computer_id: int,
    status: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Zmiana statusu komputera:
    - managed
    - exception
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


# --- Widok główny ---
@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    """
    Strona główna GUI:
    - tabela wszystkich komputerów
    - nowo znalezione (unapproved)
    - ostatnie logi wyłączeń
    """
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
