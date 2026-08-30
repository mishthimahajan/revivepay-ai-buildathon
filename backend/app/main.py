import json

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .csv_importer import parse_csv_transactions
from .database import Base, engine, get_db
from .message_generator import generate_message
from .ml_classifier import failure_classifier
from .models import (
    AuditLog,
    IdempotencyRecord,
    Transaction,
    WebhookEvent,
)
from .webhook_service import (
    extract_paid_webhook,
    verify_webhook_signature,
)
from .payment_provider import payment_provider
from .recovery_engine import recommend_recovery_action
from .schemas import (
    ActionExecutionResponse,
    ApprovalRequest,
    CSVUploadResponse,
    FailureClassificationRequest,
    FailureClassificationResponse,
    MessagePreviewRequest,
    MessagePreviewResponse,
    MetricsResponse,
    TransactionCreate,
    TransactionResponse,
    WebhookResponse,
)


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RevivePay AI API",
    description=(
        "Explainable payment-failure analysis and bounded "
        "recovery workflow using ML classification, human "
        "approval, idempotency and Razorpay test mode."
    ),
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def write_audit(
    database: Session,
    transaction: Transaction,
    event_type: str,
    actor: str,
    details: str
) -> None:
    audit = AuditLog(
        transaction=transaction,
        event_type=event_type,
        actor=actor,
        details=details
    )

    database.add(audit)


def load_transaction(
    database: Session,
    transaction_id: int
) -> Transaction | None:
    return database.scalar(
        select(Transaction)
        .options(selectinload(Transaction.audits))
        .where(Transaction.id == transaction_id)
    )


@app.get("/")
def root():
    return {
        "application": "RevivePay AI",
        "message": "Payment recovery API is running",
        "version": "2.0.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "provider_mode": settings.provider_mode,
        "ml_model_available": (
            failure_classifier.pipeline is not None
        )
    }


@app.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_transaction(
    payload: TransactionCreate,
    database: Session = Depends(get_db)
):
    decision = recommend_recovery_action(
        failure_code=payload.failure_code,
        risk_score=payload.risk_score,
        attempt_count=payload.attempt_count,
        maximum_attempts=payload.maximum_attempts,
        customer_consent=payload.customer_consent,
        do_not_contact=payload.do_not_contact
    )

    transaction = Transaction(
        **payload.model_dump(),
        recommended_action=decision.action,
        recommendation_reason=decision.reason,
        status="diagnosed"
    )

    database.add(transaction)

    try:
        database.flush()

    except IntegrityError as error:
        database.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A transaction with this payment_id "
                "already exists."
            )
        ) from error

    write_audit(
        database=database,
        transaction=transaction,
        event_type="transaction_diagnosed",
        actor="recovery-engine",
        details=(
            f"{decision.action}: {decision.reason}"
        )
    )

    database.commit()

    created_transaction = load_transaction(
        database=database,
        transaction_id=transaction.id
    )

    if created_transaction is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction could not be loaded after creation."
        )

    return created_transaction


@app.get(
    "/transactions",
    response_model=list[TransactionResponse]
)
def list_transactions(
    database: Session = Depends(get_db)
):
    query = (
        select(Transaction)
        .options(selectinload(Transaction.audits))
        .order_by(Transaction.created_at.desc())
    )

    return list(database.scalars(query).all())


@app.post(
    "/transactions/upload-csv",
    response_model=CSVUploadResponse
)
async def upload_transactions_csv(
    file: UploadFile = File(...),
    database: Session = Depends(get_db)
):
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file must have a filename."
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported."
        )

    file_content = await file.read()

    maximum_size = 2 * 1024 * 1024

    if len(file_content) > maximum_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The CSV file must be smaller than 2 MB."
        )

    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded CSV file is empty."
        )

    try:
        imported_rows, rejected_rows, errors = (
            parse_csv_transactions(
                file_content=file_content,
                database=database
            )
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from error

    return CSVUploadResponse(
        filename=file.filename,
        total_rows=imported_rows + rejected_rows,
        imported_rows=imported_rows,
        rejected_rows=rejected_rows,
        errors=errors
    )


@app.post(
    "/ai/classify-failure",
    response_model=FailureClassificationResponse
)
def classify_payment_failure(
    payload: FailureClassificationRequest
):
    result = failure_classifier.classify(
        description=payload.description
    )

    return FailureClassificationResponse(
        predicted_failure_code=(
            result.predicted_failure_code
        ),
        confidence=result.confidence,
        requires_human_review=(
            result.requires_human_review
        ),
        model_available=result.model_available,
        explanation=result.explanation
    )


@app.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse
)
def get_transaction(
    transaction_id: int,
    database: Session = Depends(get_db)
):
    transaction = load_transaction(
        database=database,
        transaction_id=transaction_id
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found."
        )

    return transaction


@app.post(
    "/transactions/{transaction_id}/message-preview",
    response_model=MessagePreviewResponse
)
def preview_recovery_message(
    transaction_id: int,
    payload: MessagePreviewRequest,
    database: Session = Depends(get_db)
):
    transaction = load_transaction(
        database=database,
        transaction_id=transaction_id
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found."
        )

    result = generate_message(
        transaction=transaction,
        language=payload.language
    )

    if result.allowed:
        event_type = "message_preview_generated"

        audit_details = (
            f"{payload.language} message preview generated "
            f"using a deterministic safety template. "
            f"Human approval is required before delivery."
        )

    else:
        event_type = "message_preview_blocked"

        audit_details = (
            f"Message preview blocked: "
            f"{result.blocked_reason}"
        )

    write_audit(
        database=database,
        transaction=transaction,
        event_type=event_type,
        actor=payload.requested_by,
        details=audit_details
    )

    database.commit()

    return MessagePreviewResponse(
        allowed=result.allowed,
        language=result.language,
        message=result.message,
        blocked_reason=result.blocked_reason,
        used_fallback=result.used_fallback,
        requires_human_approval=(
            result.requires_human_approval
        )
    )


@app.post(
    "/transactions/{transaction_id}/approve",
    response_model=ActionExecutionResponse
)
def approve_recovery_action(
    transaction_id: int,
    payload: ApprovalRequest,
    database: Session = Depends(get_db)
):
    transaction = load_transaction(
        database=database,
        transaction_id=transaction_id
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found."
        )

    existing_idempotency_record = database.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key
            == payload.idempotency_key
        )
    )

    if existing_idempotency_record is not None:
        if (
            existing_idempotency_record.transaction_id
            != transaction.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This idempotency key was already used "
                    "for another transaction."
                )
            )

        replayed_transaction = load_transaction(
            database=database,
            transaction_id=transaction.id
        )

        if replayed_transaction is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    "The previous transaction result "
                    "could not be loaded."
                )
            )

        return ActionExecutionResponse(
            message=(
                "Duplicate request detected. The previous "
                "result was returned without executing again."
            ),
            idempotent_replay=True,
            provider_reference=(
                existing_idempotency_record.provider_reference
            ),
            payment_url=(
                existing_idempotency_record.provider_url
            ),
            transaction=replayed_transaction
        )

    if transaction.recommended_action is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This transaction does not have a recovery "
                "recommendation."
            )
        )

    if transaction.recommended_action in {
        "stop_contact",
        "stop_retries"
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This transaction was stopped by the safety "
                "policy and cannot be executed."
            )
        )

    if transaction.status in {
        "recovered",
        "escalated"
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transaction is already in terminal state: "
                f"{transaction.status}."
            )
        )

    if (
        transaction.recommended_action
        == "send_payment_link"
        and transaction.provider_reference is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A Payment Link already exists for this "
                "transaction. A second link was not created."
            )
        )

    transaction.approval_status = "approved"
    transaction.approved_by = payload.approved_by

    write_audit(
        database=database,
        transaction=transaction,
        event_type="recovery_action_approved",
        actor=payload.approved_by,
        details=(
            f"Approved action: "
            f"{transaction.recommended_action}"
        )
    )

    if transaction.recommended_action == "human_review":
        transaction.status = "escalated"

        write_audit(
            database=database,
            transaction=transaction,
            event_type="transaction_escalated",
            actor="safety-policy",
            details=(
                "The transaction was escalated without "
                "performing a payment action."
            )
        )

        idempotency_record = IdempotencyRecord(
            idempotency_key=payload.idempotency_key,
            transaction_id=transaction.id,
            action="human_review",
            result_status="escalated",
            provider_reference=None,
            provider_url=None
        )

        database.add(idempotency_record)
        database.commit()

        completed_transaction = load_transaction(
            database=database,
            transaction_id=transaction.id
        )

        if completed_transaction is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    "Escalated transaction could not "
                    "be loaded."
                )
            )

        return ActionExecutionResponse(
            message=(
                "Transaction was safely escalated for "
                "human investigation."
            ),
            idempotent_replay=False,
            provider_reference=None,
            payment_url=None,
            transaction=completed_transaction
        )

    result = payment_provider.execute(
        payment_id=transaction.payment_id,
        action=transaction.recommended_action,
        amount=transaction.amount,
        currency=transaction.currency,
        customer_name=transaction.customer_name,
        customer_email=transaction.customer_email
    )

    transaction.status = result.status
    transaction.provider_reference = (
        result.provider_reference
    )
    transaction.provider_url = result.payment_url

    if result.status == "execution_failed":
        transaction.approval_status = "execution_failed"

        write_audit(
            database=database,
            transaction=transaction,
            event_type="provider_execution_failed",
            actor="payment-provider",
            details=result.message
        )

    else:
        transaction.attempt_count += 1

        write_audit(
            database=database,
            transaction=transaction,
            event_type="recovery_action_executed",
            actor="payment-provider",
            details=result.message
        )

    idempotency_record = IdempotencyRecord(
        idempotency_key=payload.idempotency_key,
        transaction_id=transaction.id,
        action=transaction.recommended_action,
        result_status=result.status,
        provider_reference=result.provider_reference,
        provider_url=result.payment_url
    )

    database.add(idempotency_record)
    database.commit()

    completed_transaction = load_transaction(
        database=database,
        transaction_id=transaction.id
    )

    if completed_transaction is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Executed transaction could not be loaded."
            )
        )

    return ActionExecutionResponse(
        message=result.message,
        idempotent_replay=False,
        provider_reference=result.provider_reference,
        payment_url=result.payment_url,
        transaction=completed_transaction
    )


@app.get(
    "/metrics",
    response_model=MetricsResponse
)
def get_metrics(
    database: Session = Depends(get_db)
):
    transactions = list(
        database.scalars(
            select(Transaction)
        ).all()
    )

    total_transactions = len(transactions)

    recovered_transactions = sum(
        transaction.status == "recovered"
        for transaction in transactions
    )

    escalated_transactions = sum(
        transaction.status == "escalated"
        for transaction in transactions
    )

    safety_stops = sum(
        transaction.recommended_action in {
            "stop_retries",
            "stop_contact"
        }
        for transaction in transactions
    )

    recovered_revenue = sum(
        transaction.recovered_amount
        for transaction in transactions
    )

    total_revenue_at_risk = sum(
        transaction.amount
        for transaction in transactions
        if transaction.status != "recovered"
    )

    recovery_rate = (
        recovered_transactions
        / total_transactions
        * 100
        if total_transactions
        else 0
    )

    return MetricsResponse(
        total_transactions=total_transactions,
        transactions_at_risk=(
            total_transactions
            - recovered_transactions
        ),
        total_revenue_at_risk=round(
            total_revenue_at_risk,
            2
        ),
        recovered_transactions=(
            recovered_transactions
        ),
        recovered_revenue=round(
            recovered_revenue,
            2
        ),
        escalated_transactions=(
            escalated_transactions
        ),
        safety_stops=safety_stops,
        recovery_rate=round(
            recovery_rate,
            2
        )
    )

@app.post(
    "/webhooks/razorpay",
    response_model=WebhookResponse,
)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(
        default=None,
        alias="X-Razorpay-Signature",
    ),
    db: Session = Depends(get_db),
) -> WebhookResponse:
    raw_body = await request.body()

    if not settings.razorpay_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay webhook secret is not configured.",
        )

    if not x_razorpay_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Razorpay-Signature header is missing.",
        )

    signature_valid = verify_webhook_signature(
        raw_body=raw_body,
        received_signature=x_razorpay_signature,
        webhook_secret=settings.razorpay_webhook_secret,
    )

    if not signature_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Razorpay webhook signature.",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body is not valid JSON.",
        ) from exc

    event_type = payload.get("event")

    # Acknowledge events that this application does not process.
    if event_type != "payment_link.paid":
        return WebhookResponse(
            accepted=True,
            processed=False,
            message=f"Event '{event_type}' was acknowledged and ignored.",
        )

    try:
        paid_event = extract_paid_webhook(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    existing_event = db.scalar(
        select(WebhookEvent).where(
            WebhookEvent.event_key == paid_event.event_key
        )
    )

    if existing_event:
        return WebhookResponse(
            accepted=True,
            processed=False,
            duplicate=True,
            message="This webhook was already processed.",
        )

    transaction = db.scalar(
        select(Transaction).where(
            Transaction.provider_reference
            == paid_event.payment_link_id
        )
    )

    if transaction is None:
        db.add(
            WebhookEvent(
                event_key=paid_event.event_key,
                event_type=paid_event.event_type,
                payment_link_id=paid_event.payment_link_id,
                payment_id=paid_event.payment_id,
                processing_status="unmatched",
                details="No matching transaction was found.",
            )
        )
        db.commit()

        return WebhookResponse(
            accepted=True,
            processed=False,
            message="Webhook verified, but no matching transaction was found.",
        )

    expected_subunits = int(round(transaction.amount * 100))

    if paid_event.currency != transaction.currency.upper():
        db.add(
            WebhookEvent(
                event_key=paid_event.event_key,
                event_type=paid_event.event_type,
                payment_link_id=paid_event.payment_link_id,
                payment_id=paid_event.payment_id,
                processing_status="currency_mismatch",
                details=(
                    f"Expected {transaction.currency}; "
                    f"received {paid_event.currency}."
                ),
            )
        )

        db.add(
            AuditLog(
                transaction_id=transaction.id,
                action="webhook_amount_mismatch",
                actor="razorpay_webhook",
                details=(
                    f"Payment {paid_event.payment_id} was not accepted "
                    "because its currency did not match."
                ),
            )
        )

        db.commit()

        return WebhookResponse(
            accepted=True,
            processed=False,
            transaction_id=transaction.id,
            message="Webhook currency did not match the transaction.",
        )

    if paid_event.amount_subunits != expected_subunits:
        db.add(
            WebhookEvent(
                event_key=paid_event.event_key,
                event_type=paid_event.event_type,
                payment_link_id=paid_event.payment_link_id,
                payment_id=paid_event.payment_id,
                processing_status="amount_mismatch",
                details=(
                    f"Expected {expected_subunits} subunits; "
                    f"received {paid_event.amount_subunits}."
                ),
            )
        )

        db.add(
    AuditLog(
        transaction_id=transaction.id,
        event_type="payment_captured",
        actor="razorpay_webhook",
        details=(
            f"Verified captured Razorpay payment "
            f"{paid_event.payment_id}. "
            f"Recovered amount: "
            f"{paid_event.amount_subunits / 100:.2f} "
            f"{paid_event.currency}."
        ),
    )
)

        db.commit()

        return WebhookResponse(
            accepted=True,
            processed=False,
            transaction_id=transaction.id,
            message="Webhook amount did not match the transaction.",
        )

    if transaction.status == "recovered":
        db.add(
            WebhookEvent(
                event_key=paid_event.event_key,
                event_type=paid_event.event_type,
                payment_link_id=paid_event.payment_link_id,
                payment_id=paid_event.payment_id,
                processing_status="already_recovered",
                details="Transaction was already marked as recovered.",
            )
        )
        db.commit()

        return WebhookResponse(
            accepted=True,
            processed=False,
            transaction_id=transaction.id,
            message="Transaction was already recovered.",
        )

    transaction.status = "recovered"
    transaction.recovered_amount = (
        paid_event.amount_subunits / 100
    )

    db.add(
        WebhookEvent(
            event_key=paid_event.event_key,
            event_type=paid_event.event_type,
            payment_link_id=paid_event.payment_link_id,
            payment_id=paid_event.payment_id,
            processing_status="processed",
            details="Captured payment verified successfully.",
        )
    )

    db.add(
        AuditLog(
            transaction_id=transaction.id,
            action="payment_captured",
            actor="razorpay_webhook",
            details=(
                f"Verified captured Razorpay payment "
                f"{paid_event.payment_id}. "
                f"Recovered amount: "
                f"{paid_event.amount_subunits / 100:.2f} "
                f"{paid_event.currency}."
            ),
        )
    )

    db.commit()
    db.refresh(transaction)

    return WebhookResponse(
        accepted=True,
        processed=True,
        transaction_id=transaction.id,
        message="Captured payment verified and transaction recovered.",
    )