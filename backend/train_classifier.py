import csv
import json
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer


BACKEND_DIRECTORY = Path(__file__).resolve().parent
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent

DATASET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "failure_training.csv"
)

ARTIFACT_DIRECTORY = BACKEND_DIRECTORY / "artifacts"
MODEL_PATH = ARTIFACT_DIRECTORY / "failure_classifier.joblib"
METRICS_PATH = ARTIFACT_DIRECTORY / "classifier_metrics.json"


def load_dataset() -> tuple[list[str], list[str]]:
    descriptions: list[str] = []
    labels: list[str] = []

    with DATASET_PATH.open(
        encoding="utf-8-sig",
        newline=""
    ) as dataset_file:
        reader = csv.DictReader(dataset_file)

        for row in reader:
            description = row["description"].strip()
            failure_code = row["failure_code"].strip()

            if description and failure_code:
                descriptions.append(description)
                labels.append(failure_code)

    return descriptions, labels


def train_model() -> None:
    descriptions, labels = load_dataset()

    if len(descriptions) < 24:
        raise ValueError(
            "The training dataset must contain at least "
            "24 labelled examples."
        )

    (
        training_descriptions,
        testing_descriptions,
        training_labels,
        testing_labels
    ) = train_test_split(
        descriptions,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels
    )

    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=3000
                )
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1500,
                    class_weight="balanced",
                    random_state=42
                )
            )
        ]
    )

    pipeline.fit(
        training_descriptions,
        training_labels
    )

    predictions = pipeline.predict(
        testing_descriptions
    )

    accuracy = accuracy_score(
        testing_labels,
        predictions
    )

    report = classification_report(
        testing_labels,
        predictions,
        output_dict=True,
        zero_division=0
    )

    ARTIFACT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    joblib.dump(
        {
            "pipeline": pipeline,
            "labels": sorted(set(labels)),
            "training_examples": len(
                training_descriptions
            ),
            "testing_examples": len(
                testing_descriptions
            )
        },
        MODEL_PATH
    )

    metrics = {
        "dataset_type": "synthetic_prototype",
        "total_examples": len(descriptions),
        "training_examples": len(
            training_descriptions
        ),
        "testing_examples": len(
            testing_descriptions
        ),
        "accuracy": round(float(accuracy), 4),
        "classification_report": report
    }

    with METRICS_PATH.open(
        "w",
        encoding="utf-8"
    ) as metrics_file:
        json.dump(
            metrics,
            metrics_file,
            indent=2
        )

    print("Model training completed.")
    print(f"Training examples: {len(training_descriptions)}")
    print(f"Testing examples: {len(testing_descriptions)}")
    print(f"Held-out accuracy: {accuracy:.4f}")
    print(f"Model saved to: {MODEL_PATH}")
    print(f"Metrics saved to: {METRICS_PATH}")


if __name__ == "__main__":
    train_model()