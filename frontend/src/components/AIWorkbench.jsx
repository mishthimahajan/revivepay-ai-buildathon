import { useState } from "react";
import {
  AlertTriangle,
  Bot,
  BrainCircuit,
  CheckCircle2,
  LoaderCircle,
  Sparkles,
} from "lucide-react";

import apiClient from "../api/client";

const EXAMPLES = [
  "The customer's card expired during payment.",
  "The payment failed because the account had insufficient funds.",
  "The bank declined the payment without providing a reason.",
];

function formatLabel(value) {
  if (!value) {
    return "Not available";
  }

  return value
    .split("_")
    .map(
      (word) =>
        word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

function AIWorkbench() {
  const [description, setDescription] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const classifyFailure = async (event) => {
    event.preventDefault();

    const cleanedDescription = description.trim();

    if (cleanedDescription.length < 5) {
      setError(
        "Enter a meaningful payment failure description.",
      );
      return;
    }

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const response = await apiClient.post(
        "/ai/classify-failure",
        {
          description: cleanedDescription,
        },
      );

      setResult(response.data);
    } catch (requestError) {
      console.error(
        "Failure classification error:",
        requestError,
      );

      const detail =
        requestError.response?.data?.detail;

      setError(
        typeof detail === "string"
          ? detail
          : "The failure could not be classified. Check the backend connection.",
      );
    } finally {
      setLoading(false);
    }
  };

  const confidencePercentage = result
    ? Math.round(Number(result.confidence || 0) * 100)
    : 0;

  return (
    <section className="ai-workbench" id="ai-workbench">
      <div className="workbench-header">
        <div>
          <p className="eyebrow">
            Interactive AI demonstration
          </p>

          <h3>
            <BrainCircuit size={25} />
            Failure Classification Workbench
          </h3>

          <p>
            Describe a payment failure and let the trained
            model identify its likely cause.
          </p>
        </div>

        <span className="ai-status-badge">
          <Sparkles size={15} />
          Explainable AI
        </span>
      </div>

      <div className="workbench-grid">
        <form
          className="classification-form"
          onSubmit={classifyFailure}
        >
          <label htmlFor="failure-description">
            Payment failure description
          </label>

          <textarea
            id="failure-description"
            value={description}
            onChange={(event) =>
              setDescription(event.target.value)
            }
            placeholder="Example: The customer's card expired while completing the payment."
            rows={6}
            maxLength={1000}
          />

          <div className="character-count">
            {description.length}/1000 characters
          </div>

          <div className="example-prompts">
            <span>Try an example:</span>

            {EXAMPLES.map((example, index) => (
              <button
                type="button"
                key={example}
                onClick={() => {
                  setDescription(example);
                  setError("");
                  setResult(null);
                }}
              >
                Example {index + 1}
              </button>
            ))}
          </div>

          {error && (
            <div className="workbench-error">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}

          <button
            className="classify-button"
            type="submit"
            disabled={loading}
          >
            {loading ? (
              <>
                <LoaderCircle
                  className="spinning"
                  size={18}
                />
                Analysing failure...
              </>
            ) : (
              <>
                <Bot size={18} />
                Classify with AI
              </>
            )}
          </button>
        </form>

        <div className="classification-result">
          {!result ? (
            <div className="result-placeholder">
              <div className="placeholder-icon">
                <BrainCircuit size={34} />
              </div>

              <h4>AI result will appear here</h4>

              <p>
                The prediction includes confidence,
                explanation, model availability and review
                requirements.
              </p>
            </div>
          ) : (
            <>
              <div className="result-heading">
                <div>
                  <span>Predicted failure</span>
                  <h4>
                    {formatLabel(
                      result.predicted_failure_code,
                    )}
                  </h4>
                </div>

                {result.requires_human_review ? (
                  <span className="review-badge required">
                    <AlertTriangle size={15} />
                    Review required
                  </span>
                ) : (
                  <span className="review-badge safe">
                    <CheckCircle2 size={15} />
                    Confident result
                  </span>
                )}
              </div>

              <div className="confidence-section">
                <div className="confidence-label">
                  <span>Model confidence</span>
                  <strong>
                    {confidencePercentage}%
                  </strong>
                </div>

                <div className="confidence-track">
                  <div
                    className="confidence-fill"
                    style={{
                      width: `${Math.min(
                        confidencePercentage,
                        100,
                      )}%`,
                    }}
                  />
                </div>
              </div>

              <div className="result-details">
                <div>
                  <span>Prediction engine</span>
                  <strong>
                    {result.model_available
                      ? "Trained ML model"
                      : "Safety fallback"}
                  </strong>
                </div>

                <div>
                  <span>Human review</span>
                  <strong>
                    {result.requires_human_review
                      ? "Required"
                      : "Not required"}
                  </strong>
                </div>
              </div>

              <div className="explanation-card">
                <span>AI explanation</span>
                <p>{result.explanation}</p>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

export default AIWorkbench;