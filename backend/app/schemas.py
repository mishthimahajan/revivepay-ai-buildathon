from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from typing import Literal


class TransactionCreate(BaseModel):
    payment_id: str = Field(min_length=3, max_length=100)
    customer_name: str = Field(min_length=2, max_length=100)

    customer_email: EmailStr | None = None

    amount: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=10)

    failure_code: str = Field(min_length=2, max_length=100)
    failure_description: str | None = None

    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)

    customer_consent: bool = True
    do_not_contact: bool = False

    attempt_count: int = Field(default=0, ge=0)
    maximum_attempts: int = Field(default=2, ge=1, le=5)


class AuditResponse(BaseModel):
    id: int
    event_type: str
    actor: str
    details: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    id: int
    payment_id: str

    customer_name: str
    customer_email: str | None

    amount: float
    currency: str

    failure_code: str
    failure_description: str | None

    risk_score: float
    customer_consent: bool
    do_not_contact: bool

    attempt_count: int
    maximum_attempts: int

    status: str
    recommended_action: str | None
    recommendation_reason: str | None

    approval_status: str
    approved_by: str | None
    provider_reference: str | None
    recovered_amount: float

    created_at: datetime
    updated_at: datetime

    audits: list[AuditResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MetricsResponse(BaseModel):
    total_transactions: int
    transactions_at_risk: int
    total_revenue_at_risk: float
    recovered_transactions: int
    recovered_revenue: float
    escalated_transactions: int
    safety_stops: int
    recovery_rate: float

class CSVRowError(BaseModel):
    row_number: int
    payment_id: str | None = None
    error: str


class CSVUploadResponse(BaseModel):
    filename: str
    total_rows: int
    imported_rows: int
    rejected_rows: int
    errors: list[CSVRowError] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    approved_by: str = Field(
        min_length=2,
        max_length=100
    )

    idempotency_key: str = Field(
        min_length=8,
        max_length=150
    )


class ActionExecutionResponse(BaseModel):
    message: str
    idempotent_replay: bool
    provider_reference: str | None = None
    transaction: TransactionResponse


class FailureClassificationRequest(BaseModel):
    description: str = Field(
        min_length=5,
        max_length=1000
    )


class FailureClassificationResponse(BaseModel):
    predicted_failure_code: str
    confidence: float
    requires_human_review: bool
    model_available: bool
    explanation: str

class MessagePreviewRequest(BaseModel):
    language: Literal["english", "hinglish"] = "english"

    requested_by: str = Field(
        min_length=2,
        max_length=100
    )


class MessagePreviewResponse(BaseModel):
    allowed: bool
    language: str
    message: str | None = None
    blocked_reason: str | None = None
    used_fallback: bool
    requires_human_approval: bool