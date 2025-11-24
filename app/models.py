# app/models.py
from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class Computer(Base):
    __tablename__ = "computers"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, index=True)
    ip = Column(String, unique=True, index=True)
    os_name = Column(String, nullable=True)
    winrm_ok = Column(Boolean, default=False)

    # Jeden status zamiast managed/approved:
    # 'found'     – znaleziony, niezarządzany
    # 'managed'   – zarządzany (wyłączany o 22:00)
    # 'exception' – wyjątek (nigdy nie wyłączamy automatycznie)
    status = Column(String(20), default="found", index=True)

    # Flaga „komputer główny / serwer”
    is_server = Column(Boolean, default=False)

    last_seen = Column(DateTime, nullable=True)
    last_user = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    exclusions = relationship(
        "DailyExclusion", back_populates="computer", cascade="all, delete-orphan"
    )
    shutdown_logs = relationship(
        "ShutdownLog", back_populates="computer", cascade="all, delete-orphan"
    )


class DailyExclusion(Base):
    """
    Dzienne wykluczenia – „Nie wyłączaj dziś”.
    Jeden wpis na (computer_id, date_for).
    """

    __tablename__ = "daily_exclusions"

    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), index=True)
    date_for = Column(Date, nullable=False, index=True)
    user_label = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    computer = relationship("Computer", back_populates="exclusions")


class ShutdownLog(Base):
    """
    Logi wyłączeń – zarówno automatycznych (22:00), jak i ręcznych.
    """

    __tablename__ = "shutdown_logs"

    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), index=True)

    scheduled_for = Column(DateTime, nullable=False)  # planowana godzina
    executed_at = Column(DateTime, nullable=True)  # kiedy faktycznie wywołano

    # status: 'success', 'failed', 'skipped_excluded', 'skipped_no_winrm', 'manual'
    status = Column(String, nullable=False)
    message = Column(Text, nullable=True)

    computer = relationship("Computer", back_populates="shutdown_logs")
