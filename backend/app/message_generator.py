from dataclasses import dataclass

from .models import Transaction


@dataclass(frozen=True)
class MessageResult:
    allowed: bool
    language: str
    message: str | None
    blocked_reason: str | None
    used_fallback: bool
    requires_human_approval: bool


def check_message_policy(
    transaction: Transaction
) -> str | None:
    if transaction.do_not_contact:
        return (
            "The customer has opted out of communication."
        )

    if not transaction.customer_consent:
        return (
            "Customer consent is missing. No recovery "
            "message may be generated for delivery."
        )

    if transaction.risk_score >= 0.80:
        return (
            "High-risk transactions must be handled "
            "internally without automated customer contact."
        )

    if transaction.recommended_action in {
        "stop_contact",
        "stop_retries",
        "human_review"
    }:
        return (
            "The recovery safety policy does not permit "
            "customer communication for this transaction."
        )

    return None


def english_template(
    transaction: Transaction
) -> str:
    customer = transaction.customer_name
    action = transaction.recommended_action

    if action == "send_payment_link":
        return (
            f"Hi {customer}, your previous payment of "
            f"INR {transaction.amount:.2f} could not be "
            f"completed. No automatic debit will be made. "
            f"You may use the secure test payment link "
            f"after reviewing the payment details."
        )

    if action == "request_customer_action":
        return (
            f"Hi {customer}, your payment requires "
            f"authentication. Please retry when convenient. "
            f"We will not attempt an automatic debit "
            f"without your action."
        )

    if action == "retry_after_cooldown":
        return (
            f"Hi {customer}, your payment could not be "
            f"processed because the banking service appears "
            f"temporarily unavailable. No immediate retry "
            f"will be made. A retry may be attempted only "
            f"after the configured cooldown."
        )

    return (
        f"Hi {customer}, your payment could not be "
        f"completed. The case has been sent for review, "
        f"and no automatic debit will be attempted."
    )


def hinglish_template(
    transaction: Transaction
) -> str:
    customer = transaction.customer_name
    action = transaction.recommended_action

    if action == "send_payment_link":
        return (
            f"Hi {customer}, aapka INR "
            f"{transaction.amount:.2f} ka previous payment "
            f"complete nahi hua. Koi automatic debit nahi "
            f"hoga. Payment details check karne ke baad "
            f"aap secure test payment link use kar sakte hain."
        )

    if action == "request_customer_action":
        return (
            f"Hi {customer}, aapke payment ke liye "
            f"authentication complete karna zaroori hai. "
            f"Aap convenient time par dobara try kar sakte "
            f"hain. Aapke action ke bina automatic debit "
            f"nahi hoga."
        )

    if action == "retry_after_cooldown":
        return (
            f"Hi {customer}, banking service temporarily "
            f"unavailable hone ki wajah se payment complete "
            f"nahi hua. Abhi koi immediate retry nahi hoga. "
            f"Configured cooldown ke baad hi retry kiya "
            f"ja sakta hai."
        )

    return (
        f"Hi {customer}, aapka payment complete nahi hua. "
        f"Case review ke liye bhej diya gaya hai aur koi "
        f"automatic debit nahi kiya jayega."
    )


def generate_message(
    transaction: Transaction,
    language: str
) -> MessageResult:
    blocked_reason = check_message_policy(transaction)

    if blocked_reason is not None:
        return MessageResult(
            allowed=False,
            language=language,
            message=None,
            blocked_reason=blocked_reason,
            used_fallback=True,
            requires_human_approval=False
        )

    if language == "hinglish":
        message = hinglish_template(transaction)
    else:
        message = english_template(transaction)

    return MessageResult(
        allowed=True,
        language=language,
        message=message,
        blocked_reason=None,
        used_fallback=True,
        requires_human_approval=True
    )