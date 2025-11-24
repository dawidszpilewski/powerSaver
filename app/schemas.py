# app/schemas.py
from datetime import datetime, date
from pydantic import BaseModel
from typing import Optional


class ComputerBase(BaseModel):
    hostname: str
    ip: str
    os_name: Optional[str] = None
    winrm_ok: bool = False

    # Pole główne do zarządzania
    status: str = "found"  # found / managed / exception

    is_server: bool = False
    last_seen: Optional[datetime] = None
    last_user: Optional[str] = None


class ComputerCreate(ComputerBase):
    pass


class ComputerUpdate(BaseModel):
    hostname: Optional[str] = None
    os_name: Optional[str] = None
    ip: Optional[str] = None
    winrm_ok: Optional[bool] = None
    status: Optional[str] = None
    is_server: Optional[bool] = None
    last_seen: Optional[datetime] = None
    last_user: Optional[str] = None


class ComputerOut(ComputerBase):
    id: int

    class Config:
        from_attributes = True


class DailyExclusionBase(BaseModel):
    computer_id: int
    date_for: date
    user_label: Optional[str] = None
    reason: Optional[str] = None


class DailyExclusionCreate(DailyExclusionBase):
    pass


class DailyExclusionOut(DailyExclusionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ShutdownLogOut(BaseModel):
    id: int
    computer_id: int
    scheduled_for: datetime
    executed_at: Optional[datetime] = None
    status: str
    message: Optional[str] = None

    class Config:
        from_attributes = True
