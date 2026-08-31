from dataclasses import dataclass

import httpx

from .config import settings


RAZORPAY_PAYMENT_LINK_URL = (
    "https://api.razorpay.com/v1/payment_links"
)


@dataclass(frozen=True)
class ProviderResult:
    success: bool
    status: str
    message: str
    provider_reference: str | None = None
    payment_url: str | None = None


class SimulatedPaymentProvider:
    def execute(
        self,
        payment_id: str,
        action: str,
        amount: float,
        currency: str = "INR",
        customer_name: str = "Test Customer",
        customer_email: str | None = None
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
                    "Revenue has not yet been recovered."
                ),
                provider_reference=(
                    f"plink_test_{payment_id}"
                ),
                payment_url=(
                    f"https://example.test/pay/{payment_id}"
                )
            )

        if action == "retry_after_cooldown":
            return ProviderResult(
                success=True,
                status="retry_scheduled",
                message=(
                    "A test retry was scheduled after "
                    "the configured cooldown."
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
                    "A customer-authentication reminder "
                    "was prepared."
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
                    "A consent request was prepared. "
                    "No payment action was executed."
                ),
                provider_reference=(
                    f"consent_test_{payment_id}"
                )
            )

        return ProviderResult(
            success=False,
            status="execution_failed",
            message=(
                f"Unsupported provider action: {action}"
            )
        )


class RazorpayTestProvider:
    def credentials_are_valid(self) -> bool:
        return (
            bool(settings.razorpay_key_id)
            and bool(settings.razorpay_key_secret)
            and settings.razorpay_key_id.startswith(
                "rzp_test_"
            )
        )

    def execute(
        self,
        payment_id: str,
        action: str,
        amount: float,
        currency: str = "INR",
        customer_name: str = "Test Customer",
        customer_email: str | None = None
    ) -> ProviderResult:
        if not self.credentials_are_valid():
            return ProviderResult(
                success=False,
                status="execution_failed",
                message=(
                    "Valid Razorpay test credentials are "
                    "not configured. Live credentials are "
                    "not permitted."
                )
            )

        if action != "send_payment_link":
            return ProviderResult(
                success=False,
                status="execution_failed",
                message=(
                    "Razorpay Payment Links are used only "
                    "for the send_payment_link action."
                )
            )

        reference_id = (
            f"revive-{payment_id}"
        )[:40]

        amount_in_subunits = int(
            round(amount * 100)
        )

        customer: dict[str, str] = {
            "name": customer_name
        }

        if customer_email:
            customer["email"] = customer_email

        request_body = {
            "amount": amount_in_subunits,
            "currency": currency.upper(),
            "accept_partial": False,
            "reference_id": reference_id,
            "description": (
                f"Test-mode recovery for {payment_id}"
            ),
            "customer": customer,
            "notify": {
                "sms": False,
                "email": False
            },
            "reminder_enable": False,
            "notes": {
                "source": "revivepay-ai",
                "environment": "test",
                "original_payment_id": payment_id
            }
        }

        try:
            with httpx.Client(
                timeout=15.0,
                auth=(
                    settings.razorpay_key_id,
                    settings.razorpay_key_secret
                )
            ) as client:
                response = client.post(
                    RAZORPAY_PAYMENT_LINK_URL,
                    json=request_body
                )

                response.raise_for_status()

            response_data = response.json()

            payment_link_id = response_data.get("id")
            payment_url = response_data.get("short_url")

            if not payment_link_id or not payment_url:
                return ProviderResult(
                    success=False,
                    status="execution_failed",
                    message=(
                        "Razorpay returned an incomplete "
                        "Payment Link response."
                    )
                )

            return ProviderResult(
                success=True,
                status="awaiting_customer_payment",
                message=(
                    "A Razorpay test-mode Payment Link was "
                    "created. Revenue remains unrecovered "
                    "until a verified captured-payment event."
                ),
                provider_reference=payment_link_id,
                payment_url=payment_url
            )

        except httpx.HTTPStatusError as error:
            try:
                error_body = error.response.json()
                provider_error = str(error_body)
            except ValueError:
                provider_error = error.response.text

            return ProviderResult(
                success=False,
                status="execution_failed",
                message=(
                    "Razorpay rejected the Payment Link "
                    f"request: {provider_error[:500]}"
                )
            )

        except httpx.RequestError as error:
            return ProviderResult(
                success=False,
                status="execution_failed",
                message=(
                    "Razorpay could not be reached. "
                    f"Network error: {str(error)[:300]}"
                )
            )


simulation_provider = SimulatedPaymentProvider()
razorpay_test_provider = RazorpayTestProvider()


def get_payment_provider():
    if settings.provider_mode == "razorpay_test":
        return razorpay_test_provider

    return simulation_provider


payment_provider = get_payment_provider()