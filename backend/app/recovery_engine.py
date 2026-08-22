from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str
    requires_approval: bool = True


def recommend_recovery_action(
    failure_code: str,
    risk_score: float,
    attempt_count: int,
    maximum_attempts: int,
    customer_consent: bool,
    do_not_contact: bool
) -> RecoveryDecision:
    code = failure_code.strip().lower()

    if do_not_contact:
        return RecoveryDecision(
            action="stop_contact",
            reason=(
                "The customer has opted out of communication. "
                "No recovery message or payment link may be sent."
            ),
            requires_approval=False
        )

    if risk_score >= 0.80 or code == "fraud_suspected":
        return RecoveryDecision(
            action="human_review",
            reason=(
                "The transaction has a high fraud-risk signal. "
                "Automated recovery is blocked."
            )
        )

    if attempt_count >= maximum_attempts:
        return RecoveryDecision(
            action="stop_retries",
            reason=(
                "The configured maximum number of recovery attempts "
                "has already been reached."
            ),
            requires_approval=False
        )

    if code in {"bank_down", "gateway_timeout", "provider_unavailable"}:
        return RecoveryDecision(
            action="retry_after_cooldown",
            reason=(
                "The failure appears temporary. Retry only after "
                "the configured cooldown period."
            )
        )

    if code in {"insufficient_funds", "card_expired"}:
        if not customer_consent:
            return RecoveryDecision(
                action="request_consent",
                reason=(
                    "A new payment method may resolve the failure, "
                    "but customer consent is required before contact."
                )
            )

        return RecoveryDecision(
            action="send_payment_link",
            reason=(
                "A new payment link allows the customer to choose "
                "a different payment method."
            )
        )

    if code in {"authentication_failed", "otp_failed"}:
        if not customer_consent:
            return RecoveryDecision(
                action="request_consent",
                reason=(
                    "Customer action is necessary, but no recovery "
                    "communication is allowed without consent."
                )
            )

        return RecoveryDecision(
            action="request_customer_action",
            reason=(
                "The payment requires customer authentication. "
                "The system must not retry it silently."
            )
        )

    return RecoveryDecision(
        action="human_review",
        reason=(
            "No approved automated playbook exists for this "
            "failure type."
        )
    )