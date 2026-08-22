from types import SimpleNamespace

from app.message_generator import generate_message


def build_transaction(**overrides):
    data = {
        "customer_name": "Riya",
        "amount": 1499.0,
        "recommended_action": "send_payment_link",
        "do_not_contact": False,
        "customer_consent": True,
        "risk_score": 0.10
    }

    data.update(overrides)

    return SimpleNamespace(**data)


def test_english_message_is_generated():
    transaction = build_transaction()

    result = generate_message(
        transaction=transaction,
        language="english"
    )

    assert result.allowed is True
    assert "automatic debit" in result.message
    assert result.requires_human_approval is True


def test_hinglish_message_is_generated():
    transaction = build_transaction()

    result = generate_message(
        transaction=transaction,
        language="hinglish"
    )

    assert result.allowed is True
    assert "aapka" in result.message
    assert "automatic debit" in result.message


def test_opted_out_customer_is_blocked():
    transaction = build_transaction(
        do_not_contact=True
    )

    result = generate_message(
        transaction=transaction,
        language="english"
    )

    assert result.allowed is False
    assert result.message is None


def test_missing_consent_is_blocked():
    transaction = build_transaction(
        customer_consent=False
    )

    result = generate_message(
        transaction=transaction,
        language="english"
    )

    assert result.allowed is False
    assert result.message is None


def test_high_risk_message_is_blocked():
    transaction = build_transaction(
        risk_score=0.91
    )

    result = generate_message(
        transaction=transaction,
        language="hinglish"
    )

    assert result.allowed is False
    assert result.message is None