from app.ml_classifier import failure_classifier


def test_bank_failure_classification():
    result = failure_classifier.classify(
        "The issuing bank servers are temporarily unavailable"
    )

    assert result.model_available is True
    assert result.predicted_failure_code == "bank_down"


def test_authentication_failure_classification():
    result = failure_classifier.classify(
        "Customer did not complete OTP authentication"
    )

    assert result.model_available is True
    assert (
        result.predicted_failure_code
        == "authentication_failed"
    )


def test_short_description_requires_review():
    result = failure_classifier.classify("bad")

    assert result.requires_human_review is True
    assert result.predicted_failure_code == "unknown_error"