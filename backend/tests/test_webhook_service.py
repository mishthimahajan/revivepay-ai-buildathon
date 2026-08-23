import hashlib
import hmac

import pytest

from app.webhook_service import (
    extract_paid_webhook,
    verify_webhook_signature,
)


def test_valid_webhook_signature():
    secret = "local-test-secret"
    body = b'{"event":"payment_link.paid"}'

    signature = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    assert verify_webhook_signature(
        raw_body=body,
        received_signature=signature,
        webhook_secret=secret,
    )


def test_invalid_webhook_signature():
    assert not verify_webhook_signature(
        raw_body=b'{"event":"payment_link.paid"}',
        received_signature="invalid-signature",
        webhook_secret="local-test-secret",
    )


def test_extract_captured_payment():
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test_123",
                    "status": "paid",
                    "amount_paid": 125000,
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "status": "captured",
                    "captured": True,
                    "amount": 125000,
                    "currency": "INR",
                }
            },
        },
    }

    result = extract_paid_webhook(payload)

    assert result.payment_link_id == "plink_test_123"
    assert result.payment_id == "pay_test_123"
    assert result.amount_subunits == 125000
    assert result.currency == "INR"


def test_reject_uncaptured_payment():
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test_123",
                    "status": "paid",
                    "amount_paid": 125000,
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "status": "authorized",
                    "captured": False,
                    "amount": 125000,
                    "currency": "INR",
                }
            },
        },
    }

    with pytest.raises(
        ValueError,
        match="Payment has not been captured",
    ):
        extract_paid_webhook(payload)