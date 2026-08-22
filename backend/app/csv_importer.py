import csv
import io

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog, Transaction
from .recovery_engine import recommend_recovery_action
from .schemas import CSVRowError, TransactionCreate


REQUIRED_COLUMNS = {
    "payment_id",
    "customer_name",
    "amount",
    "failure_code"
}


def normalise_optional(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned_value = value.strip()

    return cleaned_value if cleaned_value else None


def parse_boolean(
    value: str | None,
    default: bool
) -> bool:
    if value is None or not value.strip():
        return default

    cleaned_value = value.strip().lower()

    if cleaned_value in {"true", "1", "yes", "y"}:
        return True

    if cleaned_value in {"false", "0", "no", "n"}:
        return False

    raise ValueError(
        f"Invalid boolean value: {value}. "
        "Use true, false, yes, no, 1 or 0."
    )


def parse_csv_transactions(
    file_content: bytes,
    database: Session
) -> tuple[int, int, list[CSVRowError]]:
    try:
        decoded_content = file_content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(
            "The CSV must use UTF-8 encoding."
        ) from error

    csv_reader = csv.DictReader(
        io.StringIO(decoded_content)
    )

    if csv_reader.fieldnames is None:
        raise ValueError(
            "The uploaded CSV does not contain a header row."
        )

    supplied_columns = {
        column.strip()
        for column in csv_reader.fieldnames
        if column
    }

    missing_columns = REQUIRED_COLUMNS - supplied_columns

    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))

        raise ValueError(
            f"Required columns are missing: {missing_text}"
        )

    imported_rows = 0
    errors: list[CSVRowError] = []
    seen_payment_ids: set[str] = set()

    for row_number, row in enumerate(
        csv_reader,
        start=2
    ):
        payment_id = normalise_optional(
            row.get("payment_id")
        )

        try:
            if payment_id is None:
                raise ValueError(
                    "payment_id cannot be empty."
                )

            if payment_id in seen_payment_ids:
                raise ValueError(
                    "Duplicate payment_id inside the CSV."
                )

            existing_transaction = database.scalar(
                select(Transaction).where(
                    Transaction.payment_id == payment_id
                )
            )

            if existing_transaction is not None:
                raise ValueError(
                    "payment_id already exists in the database."
                )

            payload = TransactionCreate(
                payment_id=payment_id,
                customer_name=(
                    row.get("customer_name") or ""
                ).strip(),
                customer_email=normalise_optional(
                    row.get("customer_email")
                ),
                amount=row.get("amount", ""),
                currency=(
                    row.get("currency") or "INR"
                ).strip().upper(),
                failure_code=(
                    row.get("failure_code") or ""
                ).strip(),
                failure_description=normalise_optional(
                    row.get("failure_description")
                ),
                risk_score=row.get("risk_score") or 0.0,
                customer_consent=parse_boolean(
                    row.get("customer_consent"),
                    default=True
                ),
                do_not_contact=parse_boolean(
                    row.get("do_not_contact"),
                    default=False
                ),
                attempt_count=(
                    row.get("attempt_count") or 0
                ),
                maximum_attempts=(
                    row.get("maximum_attempts") or 2
                )
            )

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
                status="diagnosed",
                recommended_action=decision.action,
                recommendation_reason=decision.reason
            )

            database.add(transaction)
            database.flush()

            database.add(
                AuditLog(
                    transaction=transaction,
                    event_type="csv_transaction_diagnosed",
                    actor="csv-importer",
                    details=(
                        f"{decision.action}: "
                        f"{decision.reason}"
                    )
                )
            )

            seen_payment_ids.add(payment_id)
            imported_rows += 1

        except (ValueError, ValidationError) as error:
            errors.append(
                CSVRowError(
                    row_number=row_number,
                    payment_id=payment_id,
                    error=str(error)
                )
            )

    database.commit()

    return imported_rows, len(errors), errors