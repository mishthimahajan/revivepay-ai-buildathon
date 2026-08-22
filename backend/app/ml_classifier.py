from dataclasses import dataclass
from pathlib import Path

import joblib


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
MODEL_PATH = (
    BACKEND_DIRECTORY
    / "artifacts"
    / "failure_classifier.joblib"
)


@dataclass(frozen=True)
class ClassificationResult:
    predicted_failure_code: str
    confidence: float
    requires_human_review: bool
    model_available: bool
    explanation: str


class FailureClassifier:
    def __init__(self) -> None:
        self.pipeline = None
        self.labels: list[str] = []

        self.load_model()

    def load_model(self) -> None:
        if not MODEL_PATH.exists():
            return

        artifact = joblib.load(MODEL_PATH)

        self.pipeline = artifact["pipeline"]
        self.labels = artifact["labels"]

    def classify(
        self,
        description: str
    ) -> ClassificationResult:
        cleaned_description = description.strip()

        if len(cleaned_description) < 5:
            return ClassificationResult(
                predicted_failure_code="unknown_error",
                confidence=0.0,
                requires_human_review=True,
                model_available=(
                    self.pipeline is not None
                ),
                explanation=(
                    "The failure description is too short "
                    "for reliable classification."
                )
            )

        if self.pipeline is None:
            return ClassificationResult(
                predicted_failure_code="unknown_error",
                confidence=0.0,
                requires_human_review=True,
                model_available=False,
                explanation=(
                    "The classifier artifact is unavailable. "
                    "The case was safely sent for human review."
                )
            )

        probabilities = self.pipeline.predict_proba(
            [cleaned_description]
        )[0]

        classes = self.pipeline.classes_

        best_index = int(probabilities.argmax())
        predicted_code = str(classes[best_index])
        confidence = float(probabilities[best_index])

        confidence_threshold = 0.45
        requires_human_review = (
            confidence < confidence_threshold
        )

        if requires_human_review:
            explanation = (
                "Model confidence is below the 0.45 "
                "safety threshold. Human review is required."
            )
        else:
            explanation = (
                f"The classifier matched the description "
                f"to {predicted_code} with sufficient "
                f"prototype confidence."
            )

        return ClassificationResult(
            predicted_failure_code=predicted_code,
            confidence=round(confidence, 4),
            requires_human_review=requires_human_review,
            model_available=True,
            explanation=explanation
        )


failure_classifier = FailureClassifier()