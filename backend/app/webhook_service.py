from dataclasses import dataclass
import hashlib
import hmac
from typing import Any


@dataclass(frozen=True)
class PaidWebhookData:
    event_type: str
    payment_link_id: str
    payment_id: str
    amount_subunits: int
    currency: str
    event_key: str


def verify_webhook_signature(
    raw_body: bytes,
    received_signature: str,
    webhook_secret: str,
) -> bool:
    if not raw_body or not received_signature or not webhook_secret:
        return False

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected_signature,
        received_signature,
    )


def extract_paid_webhook(payload: dict[str, Any]) -> PaidWebhookData:
    event_type = payload.get("event")

    if event_type != "payment_link.paid":
        raise ValueError("Unsupported webhook event.")

    webhook_payload = payload.get("payload")

    if not isinstance(webhook_payload, dict):
        raise ValueError("Webhook payload is missing.")

    link_wrapper = webhook_payload.get("payment_link")
    payment_wrapper = webhook_payload.get("payment")

    if not isinstance(link_wrapper, dict):
        raise ValueError("Payment Link entity is missing.")

    if not isinstance(payment_wrapper, dict):
        raise ValueError("Payment entity is missing.")

    link = link_wrapper.get("entity")
    payment = payment_wrapper.get("entity")

    if not isinstance(link, dict) or not isinstance(payment, dict):
        raise ValueError("Webhook entity is invalid.")

    payment_link_id = link.get("id")
    payment_id = payment.get("id")
    link_status = link.get("status")
    payment_status = payment.get("status")
    captured = payment.get("captured")

    amount_paid = link.get("amount_paid")
    payment_amount = payment.get("amount")
    currency = payment.get("currency")

    if not isinstance(payment_link_id, str) or not payment_link_id:
        raise ValueError("Payment Link ID is missing.")

    if not isinstance(payment_id, str) or not payment_id:
        raise ValueError("Payment ID is missing.")

    if link_status != "paid":
        raise ValueError("Payment Link is not marked as paid.")

    if payment_status != "captured" or captured is not True:
        raise ValueError("Payment has not been captured.")

    if not isinstance(amount_paid, int) or amount_paid < 1:
        raise ValueError("Invalid Payment Link amount.")

    if not isinstance(payment_amount, int) or payment_amount < 1:
        raise ValueError("Invalid payment amount.")

    if amount_paid != payment_amount:
        raise ValueError("Payment amount does not match Payment Link amount.")

    if not isinstance(currency, str) or not currency:
        raise ValueError("Payment currency is missing.")

    event_source = (
        f"{event_type}:{payment_link_id}:{payment_id}"
    )

    event_key = hashlib.sha256(
        event_source.encode("utf-8")
    ).hexdigest()

    return PaidWebhookData(
        event_type=event_type,
        payment_link_id=payment_link_id,
        payment_id=payment_id,
        amount_subunits=payment_amount,
        currency=currency.upper(),
        event_key=event_key,
    )