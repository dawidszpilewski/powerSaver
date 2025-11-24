# app/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List
import socket
from ipaddress import ip_network

from .database import SessionLocal
from .config import settings
from . import crud, schemas, models
from .winrm_utils import get_winrm_info, shutdown_via_winrm

scheduler = AsyncIOScheduler()


def scan_network():
    """
    Skan sieci – szuka hostów z otwartym portem 5985 (WinRM),
    przez WinRM pobiera hostname + zalogowanego użytkownika
    i aktualizuje/dopisuje rekordy w bazie.
    Nowo wykryte dostają status 'found'.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        print(f"[{now}] Skanowanie sieci (port 5985 / WinRM)...")

        networks = [net.strip() for net in settings.NETWORKS.split(";") if net.strip()]

        for net in networks:
            try:
                net_obj = ip_network(net, strict=False)
            except ValueError as e:
                print(f"Nieprawidlowy zakres sieci '{net}': {e}")
                continue

            for ip in net_obj.hosts():
                ip_str = str(ip)

                # 1) Czy port 5985 jest otwarty?
                try:
                    with socket.create_connection((ip_str, 5985), timeout=0.5):
                        port_open = True
                except OSError:
                    port_open = False

                if not port_open:
                    continue

                # 2) Rekord w DB?
                existing = crud.get_computer_by_ip(db, ip_str)
                now = datetime.utcnow()

                if existing is None:
                    # Nowo znaleziony komputer
                    comp_create = schemas.ComputerCreate(
                        hostname=ip_str,   # tymczasowo IP, zaraz poprawimy z WinRM
                        ip=ip_str,
                        os_name="Windows",
                        winrm_ok=False,
                        managed=False,
                        approved=False,
                        is_server=False,
                        status="found",
                        last_seen=now,
                        last_user=None,
                    )
                    comp = crud.create_computer(db, comp_create)
                else:
                    comp = existing
                    # jeśli status jest None (stare rekordy), traktujemy jako 'found'
                    if comp.status is None:
                        comp.status = "found"
                    update_data = schemas.ComputerUpdate(
                        last_seen=now,
                        os_name=comp.os_name or "Windows",
                    )
                    crud.update_computer(db, comp, update_data)

                # 3) WinRM – pobieramy hostname + zalogowanego usera
                success, hostname, current_user, err = get_winrm_info(ip_str)

                if not success:
                    print(f"[WinRM ERROR] {ip_str}: {err}")

                # hostname z WinRM > hostname z DB > IP
                new_hostname = hostname or comp.hostname or ip_str

                update_data = schemas.ComputerUpdate(
                    hostname=new_hostname,
                    winrm_ok=success,
                    last_user=current_user,
                )
                crud.update_computer(db, comp, update_data)

        print(f"[{datetime.utcnow()}] Skan sieci zakonczony.")
    finally:
        db.close()


def shutdown_managed_computers():
    """
    Wyłącza komputery o 22:00, z poszanowaniem wykluczeń dziennych.
    Na razie możesz mieć ten job niepodpięty, dopóki testujesz.
    """
    db: Session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Rozpoczynam wyłączanie komputerów...")
        computers: List[models.Computer] = db.query(models.Computer).filter(
            models.Computer.status == "managed",
            models.Computer.winrm_ok == True,
        ).all()

        now = datetime.utcnow()
        today = date.today()

        for comp in computers:
            if crud.exists_daily_exclusion_for_today(db, comp.id):
                crud.create_shutdown_log(
                    db,
                    computer_id=comp.id,
                    scheduled_for=datetime.combine(today, datetime.min.time()).replace(
                        hour=22, minute=0, second=0
                    ),
                    status="skipped_excluded",
                    message="Excluded for today",
                    executed_at=now,
                )
                continue

            success, msg = shutdown_via_winrm(comp.ip)
            status = "success" if success else "failed"
            crud.create_shutdown_log(
                db,
                computer_id=comp.id,
                scheduled_for=datetime.combine(today, datetime.min.time()).replace(
                    hour=22, minute=0, second=0
                ),
                status=status,
                message=msg,
                executed_at=now,
            )

        print(f"[{datetime.now()}] Proba wyłączania zakonczona.")
    finally:
        db.close()


def start_scheduler():
    # Skanowanie 3x dziennie: 10:00, 13:00, 16:00
    scheduler.add_job(scan_network, CronTrigger(hour="10,13,16", minute=0))

    # Job wyłączania na razie możesz zostawić zakomentowany
    # scheduler.add_job(shutdown_managed_computers, CronTrigger(hour=22, minute=0))

    scheduler.start()
