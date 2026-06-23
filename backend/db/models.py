"""SQLAlchemy ORM models for the Security Monitoring System."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Incident(Base):
    """ORM model for the incidents table.

    Stores security violation records with metadata and evidence paths.
    """

    __tablename__ = "incidents"

    incident_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    camera_name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    screenshot_path: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default=""
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="Pending Review"
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_incidents_confidence"
        ),
        CheckConstraint(
            "status IN ('Pending Review', 'Confirmed', 'False Alarm')",
            name="ck_incidents_status",
        ),
        Index("idx_incidents_timestamp", "timestamp", postgresql_using="btree"),
        Index("idx_incidents_type", "incident_type"),
        Index("idx_incidents_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Incident(incident_id={self.incident_id}, "
            f"type={self.incident_type}, status={self.status})>"
        )


class AuditLog(Base):
    """ORM model for the audit_logs table.

    Records system events such as incident status changes, system startups,
    configuration updates, and detection events for compliance tracking.
    """

    __tablename__ = "audit_logs"

    log_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="system"
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")

    __table_args__ = (
        Index("idx_audit_logs_timestamp", "timestamp", postgresql_using="btree"),
        Index("idx_audit_logs_event_type", "event_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(log_id={self.log_id}, "
            f"event_type={self.event_type}, actor={self.actor})>"
        )


class DeskZoneConfig(Base):
    """ORM model for the desk_zone_config table.

    Singleton row (id=1) storing the configurable desk zone boundaries
    as percentage values relative to the camera frame dimensions.
    """

    __tablename__ = "desk_zone_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    x1_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="20"
    )
    y1_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="35"
    )
    x2_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="80"
    )
    y2_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="75"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_desk_zone_singleton"),
        CheckConstraint(
            "x1_percent >= 0 AND x1_percent <= 100", name="ck_desk_zone_x1"
        ),
        CheckConstraint(
            "y1_percent >= 0 AND y1_percent <= 100", name="ck_desk_zone_y1"
        ),
        CheckConstraint(
            "x2_percent >= 0 AND x2_percent <= 100", name="ck_desk_zone_x2"
        ),
        CheckConstraint(
            "y2_percent >= 0 AND y2_percent <= 100", name="ck_desk_zone_y2"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DeskZoneConfig(x1={self.x1_percent}%, y1={self.y1_percent}%, "
            f"x2={self.x2_percent}%, y2={self.y2_percent}%)>"
        )
