"""Pydantic models for persistence layer."""

from pydantic import BaseModel, Field
from typing import Optional


class AccountRecord(BaseModel):
    """Account stored in database."""
    id: Optional[int] = None
    login: int
    encrypted_password: str
    server: str
    role: str = "slave"  # master | slave
    enabled: bool = True
    display_name: str = ""
    settings_json: str = "{}"


class TradeMappingRecord(BaseModel):
    """Master-to-slave trade mapping."""
    id: Optional[int] = None
    master_uuid: str
    master_ticket: int
    master_login: int
    slave_ticket: Optional[int] = None
    slave_login: int
    symbol: str
    direction: str
    master_lot: float
    slave_lot: Optional[float] = None
    status: str = "pending"


class TradeHistoryRecord(BaseModel):
    """Trade lifecycle event record."""
    id: Optional[int] = None
    master_uuid: Optional[str] = None
    account_login: int
    ticket: int
    symbol: str
    trade_type: str  # market | pending
    direction: str   # buy | sell
    volume: float
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    profit: Optional[float] = None
    commission: float = 0.0
    swap: float = 0.0
    event: str  # opened | closed | modified | partial_close | sl_tp_update


class SystemConfigRecord(BaseModel):
    """System config key-value pair."""
    key: str
    value: str


class AuditLogRecord(BaseModel):
    """Audit log entry."""
    id: Optional[int] = None
    event_type: str
    details: str = "{}"
    timestamp: Optional[str] = None
