"""
CA Service Database Models and Configuration
Uses SQLite for certificate storage and audit logging.
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pathlib import Path

UTC = timezone.utc

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ca_service.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


class IssuedCertificate(Base):
    """Stores issued certificates"""
    __tablename__ = "issued_certificates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String(100), unique=True, nullable=False, index=True)
    plugin_id = Column(String(120), nullable=False, index=True)
    status = Column(String(20), default="active")  # active, revoked, expired
    issued_at = Column(DateTime, default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(200), nullable=True)
    cert_pem = Column(Text, nullable=False)
    
    def to_dict(self):
        return {
            "id": self.id,
            "serial_number": self.serial_number,
            "plugin_id": self.plugin_id,
            "status": self.status,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revocation_reason": self.revocation_reason
        }


class CertificateAuditLog(Base):
    """Audit log for all certificate operations"""
    __tablename__ = "certificate_audit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    operation = Column(String(50), nullable=False)  # ISSUE, VERIFY, REVOKE, REJECT
    plugin_id = Column(String(120), nullable=True)
    serial_number = Column(String(100), nullable=True)
    success = Column(Boolean, default=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "operation": self.operation,
            "plugin_id": self.plugin_id,
            "serial_number": self.serial_number,
            "success": self.success,
            "details": self.details,
            "ip_address": self.ip_address
        }


class RevokedCertificate(Base):
    """Certificate Revocation List (CRL)"""
    __tablename__ = "revoked_certificates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String(100), unique=True, nullable=False, index=True)
    plugin_id = Column(String(120), nullable=False)
    revoked_at = Column(DateTime, default=lambda: datetime.now(UTC))
    reason = Column(String(200), default="unspecified")


def get_db():
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("[CA SERVICE DB] Database initialized: ca_service.db")
