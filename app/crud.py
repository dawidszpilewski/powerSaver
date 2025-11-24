# app/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date, datetime
from typing import List, Optional

from . import models, schemas


def get_all_computers(db: Session) -> List[models.Computer]:
    """Zwraca wszystkie komputery, posortowane po hostname."""
    return db.query(models.Computer).order_by(models.Computer.hostname).all()


def get_computer_by_ip(db: Session, ip: str) -> Optional[models.Computer]:
    return db.query(models.Computer).filter(models.Computer.ip == ip).first()


def get_computer(db: Session, computer_id: int) -> Optional[models.Computer]:
    return db.query(models.Computer).filter(models.Computer.id == computer_id).first()


def create_computer(db: Session, comp: schemas.ComputerCreate) -> models.Computer:
    db_obj = models.Computer(**comp.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_computer(
    db: Session,
    computer: models.Computer,
    data: schemas.ComputerUpdate
) -> models.Computer:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(computer, field, value)
    db.add(computer)
    db.commit()
    db.refresh(computer)
    return computer


# --- Wykluczenia dzienne (nie wyłączaj dziś) ---


def create_daily_exclusion(
    db: Session,
    data: schemas.DailyExclusionCreate
) -> models.DailyExclusion:
    db_obj = models.DailyExclusion(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def exists_daily_exclusion_for_today(db: Session, computer_id: int) -> bool:
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
        is not None
    )


# --- Logi wyłączeń ---


def create_shutdown_log(
    db: Session,
    computer_id: int,
    scheduled_for: datetime,
    status: str,
    message: Optional[str] = None,
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


def get_recent_shutdown_logs(
    db: Session,
    limit: int = 50
) -> List[models.ShutdownLog]:
    return (
        db.query(models.ShutdownLog)
        .order_by(models.ShutdownLog.scheduled_for.desc())
        .limit(limit)
        .all()
    )
