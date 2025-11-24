# app/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, Date, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Computer(Base):
    __tablename__ = "computers"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, index=True)
    ip = Column(String, index=True)
    os_name = Column(String, nullable=True)
    winrm_ok = Column(Boolean, default=False)

    # stare pola możesz zostawić, ale nie będziemy ich używać:
    managed = Column(Boolean, default=False)
    approved = Column(Boolean, default=False)
    is_server = Column(Boolean, default=False)

    # 🔹 NOWE POLE – tryb:
    # "found"     -> Znaleziony
    # "managed"   -> Zarządzany (kandydat do wyłączania)
    # "exception" -> Wyjątek (nigdy nie wyłączamy automatycznie)
    status = Column(String, default="found", index=True)

    last_seen = Column(DateTime, nullable=True)
    last_user = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    exclusions = relationship("DailyExclusion", back_populates="computer")
    shutdown_logs = relationship("ShutdownLog", back_populates="computer")



class DailyExclusion(Base):
    __tablename__ = "daily_exclusions"

    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), index=True)
    date_for = Column(Date, index=True)
    user_label = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    computer = relationship("Computer", back_populates="exclusions")


class ShutdownLog(Base):
    __tablename__ = "shutdown_logs"

    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), index=True)
    scheduled_for = Column(DateTime, nullable=False)
    executed_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)   # success / failed / skipped_excluded / ...
    message = Column(Text, nullable=True)

    computer = relationship("Computer", back_populates="shutdown_logs")
