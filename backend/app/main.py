from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    status
)
from fastapi.middleware.cors import CORSMiddleware
from .csv_importer import parse_csv_transactions
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from .config import settings
from .database import Base, engine, get_db


from .ml_classifier import failure_classifier

from .recovery_engine import recommend_recovery_action

from .models import (
    AuditLog,
    IdempotencyRecord,
    Transaction
)
from .payment_provider import payment_provider
from .schemas import (
    ActionExecutionResponse,
    ApprovalRequest,
    CSVUploadResponse,
    FailureClassificationRequest,
    FailureClassificationResponse,
    MetricsResponse,
    TransactionCreate,
    TransactionResponse
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RevivePay AI API",
    description=(
        "Explainable payment-failure analysis and bounded "
        "recovery workflow."
    ),
    version="1.0.0"
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
    database.add(
        AuditLog(
            transaction=transaction,
            event_type=event_type,
            actor=actor,
            details=details
        )
    )
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
        "message": "Payment recovery API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "provider_mode": settings.provider_mode
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
    except IntegrityError:
        database.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A transaction with this payment_id already exists."
        )

    write_audit(
        database=database,
        transaction=transaction,
        event_type="transaction_diagnosed",
        actor="recovery-engine",
        details=f"{decision.action}: {decision.reason}"
    )

    database.commit()

    return database.scalar(
        select(Transaction)
        .options(selectinload(Transaction.audits))
        .where(Transaction.id == transaction.id)
    )


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


@app.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse
)
def get_transaction(
    transaction_id: int,
    database: Session = Depends(get_db)
):
    transaction = database.scalar(
        select(Transaction)
        .options(selectinload(Transaction.audits))
        .where(Transaction.id == transaction_id)
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found."
        )

    return transaction

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


@app.get(
    "/metrics",
    response_model=MetricsResponse
)
def get_metrics(
    database: Session = Depends(get_db)
):
    transactions = list(
        database.scalars(select(Transaction)).all()
    )

    total_transactions = len(transactions)

    recovered_transactions = sum(
        transaction.status == "recovered"
        for transaction in transactions
    )

    escalated_transactions = sum(
        transaction.recommended_action == "human_review"
        for transaction in transactions
    )

    safety_stops = sum(
        transaction.recommended_action
        in {"stop_retries", "stop_contact"}
        for transaction in transactions
    )

    recovered_revenue = sum(
        transaction.recovered_amount
        for transaction in transactions
    )

    total_revenue_at_risk = sum(
        transaction.amount
        for transaction in transactions
    )

    recovery_rate = (
        recovered_transactions / total_transactions * 100
        if total_transactions
        else 0
    )

    return MetricsResponse(
        total_transactions=total_transactions,
        transactions_at_risk=(
            total_transactions - recovered_transactions
        ),
        total_revenue_at_risk=round(total_revenue_at_risk, 2),
        recovered_transactions=recovered_transactions,
        recovered_revenue=round(recovered_revenue, 2),
        escalated_transactions=escalated_transactions,
        safety_stops=safety_stops,
        recovery_rate=round(recovery_rate, 2)
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

        return ActionExecutionResponse(
            message=(
                "Duplicate request detected. The previous "
                "result was returned without executing again."
            ),
            idempotent_replay=True,
            provider_reference=(
                existing_idempotency_record.provider_reference
            ),
            transaction=replayed_transaction
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
            provider_reference=None
        )

        database.add(idempotency_record)
        database.commit()

        completed_transaction = load_transaction(
            database=database,
            transaction_id=transaction.id
        )

        return ActionExecutionResponse(
            message=(
                "Transaction was safely escalated for "
                "human investigation."
            ),
            idempotent_replay=False,
            provider_reference=None,
            transaction=completed_transaction
        )

    result = payment_provider.execute(
        payment_id=transaction.payment_id,
        action=transaction.recommended_action,
        amount=transaction.amount
    )

    transaction.status = result.status
    transaction.provider_reference = (
        result.provider_reference
    )

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
        provider_reference=result.provider_reference
    )

    database.add(idempotency_record)
    database.commit()

    completed_transaction = load_transaction(
        database=database,
        transaction_id=transaction.id
    )

    return ActionExecutionResponse(
        message=result.message,
        idempotent_replay=False,
        provider_reference=result.provider_reference,
        transaction=completed_transaction
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