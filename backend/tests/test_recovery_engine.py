from app.recovery_engine import recommend_recovery_action


def test_high_risk_payment_goes_to_human_review():
    decision = recommend_recovery_action(
        failure_code="bank_down",
        risk_score=0.91,
        attempt_count=0,
        maximum_attempts=2,
        customer_consent=True,
        do_not_contact=False
    )

    assert decision.action == "human_review"


def test_attempt_limit_stops_recovery():
    decision = recommend_recovery_action(
        failure_code="gateway_timeout",
        risk_score=0.10,
        attempt_count=2,
        maximum_attempts=2,
        customer_consent=True,
        do_not_contact=False
    )

    assert decision.action == "stop_retries"


def test_opted_out_customer_is_not_contacted():
    decision = recommend_recovery_action(
        failure_code="insufficient_funds",
        risk_score=0.10,
        attempt_count=0,
        maximum_attempts=2,
        customer_consent=True,
        do_not_contact=True
    )

    assert decision.action == "stop_contact"


def test_insufficient_funds_creates_payment_link_action():
    decision = recommend_recovery_action(
        failure_code="insufficient_funds",
        risk_score=0.10,
        attempt_count=0,
        maximum_attempts=2,
        customer_consent=True,
        do_not_contact=False
    )

    assert decision.action == "send_payment_link"


def test_unknown_error_requires_review():
    decision = recommend_recovery_action(
        failure_code="unmapped_provider_error",
        risk_score=0.20,
        attempt_count=0,
        maximum_attempts=2,
        customer_consent=True,
        do_not_contact=False
    )

    assert decision.action == "human_review"