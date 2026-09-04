import {
  Check,
  Circle,
  ShieldAlert,
  X,
} from "lucide-react";

function hasAudit(transaction, eventType) {
  return Boolean(
    transaction.audits?.some(
      (audit) => audit.event_type === eventType,
    ),
  );
}

function RecoveryTimeline({ transaction }) {
  const action = transaction.recommended_action;
  const status = transaction.status;

  const safetyBlocked = [
    "stop_contact",
    "stop_retries",
  ].includes(action);

  const escalated =
    status === "escalated" ||
    action === "human_review";

  const approved =
    transaction.approval_status === "approved" ||
    hasAudit(
      transaction,
      "recovery_action_approved",
    );

  const executed =
    [
      "payment_link_created",
      "awaiting_customer_consent",
      "recovered",
      "execution_failed",
    ].includes(status) ||
    hasAudit(
      transaction,
      "recovery_action_executed",
    );

  const executionFailed =
    status === "execution_failed" ||
    hasAudit(
      transaction,
      "provider_execution_failed",
    );

  let steps;

  if (safetyBlocked) {
    steps = [
      {
        label: "Diagnosed",
        description: "Failure analysed",
        completed: true,
      },
      {
        label: "Safety Block",
        description:
          action === "stop_contact"
            ? "Customer contact prevented"
            : "Further retries prevented",
        completed: true,
        blocked: true,
      },
    ];
  } else if (escalated) {
    steps = [
      {
        label: "Diagnosed",
        description: "Failure analysed",
        completed: true,
      },
      {
        label: "Human Review",
        description: "Escalated for investigation",
        completed: true,
      },
    ];
  } else {
    steps = [
      {
        label: "Diagnosed",
        description: "AI recommendation generated",
        completed: true,
      },
      {
        label: "Approved",
        description: "Human approval received",
        completed: approved,
      },
      {
        label: executionFailed
          ? "Execution Failed"
          : "Executed",
        description: executionFailed
          ? "Provider action failed"
          : "Recovery action executed",
        completed: executed,
        failed: executionFailed,
      },
      {
        label: "Recovered",
        description: "Payment captured and verified",
        completed: status === "recovered",
      },
    ];
  }

  const firstIncompleteIndex = steps.findIndex(
    (step) => !step.completed,
  );

  return (
    <section className="recovery-timeline">
      <div className="timeline-heading">
        <div>
          <span>Recovery workflow</span>
          <h4>Transaction progress</h4>
        </div>

        <span className="timeline-status">
          {safetyBlocked
            ? "Safety stopped"
            : executionFailed
              ? "Action required"
              : status === "recovered"
                ? "Completed"
                : "In progress"}
        </span>
      </div>

      <div className="timeline-steps">
        {steps.map((step, index) => {
          const current =
            firstIncompleteIndex === index;

          return (
            <div
              className={[
                "timeline-step",
                step.completed ? "completed" : "",
                current ? "current" : "",
                step.blocked ? "blocked" : "",
                step.failed ? "failed" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              key={step.label}
            >
              <div className="timeline-marker">
                {step.failed ? (
                  <X size={15} />
                ) : step.blocked ? (
                  <ShieldAlert size={15} />
                ) : step.completed ? (
                  <Check size={15} />
                ) : (
                  <Circle size={11} />
                )}
              </div>

              <div className="timeline-copy">
                <strong>{step.label}</strong>
                <span>{step.description}</span>
              </div>

              {index < steps.length - 1 && (
                <div className="timeline-line" />
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default RecoveryTimeline;