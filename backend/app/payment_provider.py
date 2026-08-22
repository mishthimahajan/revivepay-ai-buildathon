from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderResult:
    success: bool
    status: str
    message: str
    provider_reference: str | None = None


class SimulatedPaymentProvider:
    """
    Repeatable provider used before Razorpay test-mode integration.

    It does not process real payments or contact real customers.
    """

    def execute(
        self,
        payment_id: str,
        action: str,
        amount: float
    ) -> ProviderResult:
        if payment_id.endswith("006"):
            return ProviderResult(
                success=False,
                status="execution_failed",
                message=(
                    "Simulated payment-provider timeout. "
                    "No action was completed."
                )
            )

        if action == "send_payment_link":
            return ProviderResult(
                success=True,
                status="awaiting_customer_payment",
                message=(
                    "A simulated test payment link was created. "
                    "Revenue is not considered recovered until "
                    "a verified payment event is received."
                ),
                provider_reference=(
                    f"plink_test_{payment_id}"
                )
            )

        if action == "retry_after_cooldown":
            return ProviderResult(
                success=True,
                status="retry_scheduled",
                message=(
                    "A test-mode retry was scheduled after "
                    "the required cooldown."
                ),
                provider_reference=(
                    f"retry_test_{payment_id}"
                )
            )

        if action == "request_customer_action":
            return ProviderResult(
                success=True,
                status="awaiting_customer_action",
                message=(
                    "A customer-authentication reminder was "
                    "prepared for approval."
                ),
                provider_reference=(
                    f"message_test_{payment_id}"
                )
            )

        if action == "request_consent":
            return ProviderResult(
                success=True,
                status="awaiting_customer_consent",
                message=(
                    "A consent request was prepared. No payment "
                    "action was executed."
                ),
                provider_reference=(
                    f"consent_test_{payment_id}"
                )
            )

        return ProviderResult(
            success=False,
            status="execution_failed",
            message=(
                f"The provider does not support action: {action}"
            )
        )


payment_provider = SimulatedPaymentProvider()