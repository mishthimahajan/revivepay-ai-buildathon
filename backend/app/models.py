from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)

    payment_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True
    )

    customer_name: Mapped[str] = mapped_column(String(100))
    customer_email: Mapped[str | None] = mapped_column(String(150), nullable=True)

    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="INR")

    failure_code: Mapped[str] = mapped_column(String(100))
    failure_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    customer_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    maximum_attempts: Mapped[int] = mapped_column(Integer, default=2)

    status: Mapped[str] = mapped_column(
        String(50),
        default="detected"
    )

    recommended_action: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    recommendation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    approval_status: Mapped[str] = mapped_column(
        String(50),
        default="pending"
    )

    approved_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    provider_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )
    provider_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    recovered_amount: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    audits: Mapped[list["AuditLog"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan"
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"),
        index=True
    )

    event_type: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    transaction: Mapped[Transaction] = relationship(
        back_populates="audits"
    )

class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(primary_key=True)

    idempotency_key: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True
    )

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"),
        index=True
    )

    action: Mapped[str] = mapped_column(String(100))
    result_status: Mapped[str] = mapped_column(String(100))

    provider_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )
    provider_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    event_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    payment_link_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    payment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="received",
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
