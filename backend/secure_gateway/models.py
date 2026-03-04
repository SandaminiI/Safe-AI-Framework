from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Integer, Boolean, Index, Text

UTC = timezone.utc


class Base(DeclarativeBase):
    pass


class Plugin(Base):
    __tablename__ = "plugins"

    plugin_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(80), default="")
    declared_intent: Mapped[str] = mapped_column(String(120), default="")
    trust_score: Mapped[float] = mapped_column(Float, default=100.0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    service_base_url: Mapped[str] = mapped_column(String(300), default="")

    # ── Zero-Trust behavioural tracking ──────────────────────────────────
    last_request_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    request_frequency: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    last_anomaly_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(120), index=True)
    path: Mapped[str] = mapped_column(String(300))
    method: Mapped[str] = mapped_column(String(10))
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    error_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class TrustEvent(Base):
    """Immutable audit log of every trust-score change."""
    __tablename__ = "trust_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(40))       # recovery | penalty
    delta: Mapped[float] = mapped_column(Float)
    score_before: Mapped[float] = mapped_column(Float)
    score_after: Mapped[float] = mapped_column(Float)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


Index("idx_logs_plugin_time", RequestLog.plugin_id, RequestLog.created_at)
Index("idx_trust_events_plugin", TrustEvent.plugin_id, TrustEvent.created_at)