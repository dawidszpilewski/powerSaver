# app/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date, datetime
from typing import List, Optional

from . import models, schemas


# ---------- KOMPUTERY ----------

def get_all_computers(db: Session) -> List[models.Computer]:
    return db.query(models.Computer).order_by(models.Computer.hostname).all()


def get_computer(db: Session, computer_id: int) -> Optional[models.Computer]:
    return db.query(models.Computer).filter(models.Computer.id == computer_id).first()


def get_computer_by_ip(db: Session, ip: str) -> Optional[models.Computer]:
    return db.query(models.Computer).filter(models.Computer.ip == ip).first()


def create_computer(db: Session, comp_in: schemas.ComputerCreate) -> models.Computer:
    obj = models.Computer(
        hostname=comp_in.hostname,
        ip=comp_in.ip,
        os_name=comp_in.os_name,
        winrm_ok=comp_in.winrm_ok,
        status=comp_in.status,
        is_server=comp_in.is_server,
        last_seen=comp_in.last_seen,
        last_user=comp_in.last_user,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_computer(
    db: Session, computer: models.Computer, comp_in: schemas.ComputerUpdate
) -> models.Computer:
    data = comp_in.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(computer, field, value)
    computer.updated_at = datetime.utcnow()
    db.add(computer)
    db.commit()
    db.refresh(computer)
    return computer


# ---------- WYKLUCZENIA DZIENNE ----------

def get_daily_exclusion_for_today(
    db: Session, computer_id: int
) -> Optional[models.DailyExclusion]:
    today = date.today()
    return (
        db.query(models.DailyExclusion)
        .filter(
            and_(
                models.DailyExclusion.computer_id == computer_id,
                models.DailyExclusion.date_for == today,
            )
        )
        .first()
    )


def exists_daily_exclusion_for_today(db: Session, computer_id: int) -> bool:
    return get_daily_exclusion_for_today(db, computer_id) is not None


def create_daily_exclusion(
    db: Session, data: schemas.DailyExclusionCreate
) -> models.DailyExclusion:
    obj = models.DailyExclusion(
        computer_id=data.computer_id,
        date_for=data.date_for,
        user_label=data.user_label,
        reason=data.reason,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_daily_exclusion_for_today(db: Session, computer_id: int) -> None:
    obj = get_daily_exclusion_for_today(db, computer_id)
    if obj:
        db.delete(obj)
        db.commit()


def get_today_exclusions(db: Session) -> List[models.DailyExclusion]:
    today = date.today()
    return (
        db.query(models.DailyExclusion)
        .filter(models.DailyExclusion.date_for == today)
        .all()
    )


# ---------- LOGI WYŁĄCZEŃ ----------

def create_shutdown_log(
    db: Session,
    computer_id: int,
    scheduled_for: datetime,
    status: str,
    message: Optional[str],
    executed_at: Optional[datetime] = None,
) -> models.ShutdownLog:
    obj = models.ShutdownLog(
        computer_id=computer_id,
        scheduled_for=scheduled_for,
        executed_at=executed_at,
        status=status,
        message=message,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_recent_shutdown_logs(db: Session, limit: int = 50) -> List[models.ShutdownLog]:
    return (
        db.query(models.ShutdownLog)
        .order_by(models.ShutdownLog.scheduled_for.desc())
        .limit(limit)
        .all()
    )
