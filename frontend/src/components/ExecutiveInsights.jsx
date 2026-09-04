import {
  AlertTriangle,
  Download,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";

function formatAction(value) {
  if (!value) {
    return "Unknown";
  }

  return value
    .split("_")
    .map(
      (word) =>
        word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

function escapeCSV(value) {
  const text = String(value ?? "");

  return `"${text.replaceAll('"', '""')}"`;
}

function ExecutiveInsights({ transactions }) {
  const highRiskTransactions = transactions.filter(
    (transaction) =>
      Number(transaction.risk_score) >= 0.65,
  );

  const humanReviewTransactions =
    transactions.filter(
      (transaction) =>
        transaction.recommended_action ===
          "human_review" ||
        transaction.status === "escalated",
    );

  const safetyProtectedTransactions =
    transactions.filter((transaction) =>
      ["stop_contact", "stop_retries"].includes(
        transaction.recommended_action,
      ),
    );

  const actionableTransactions =
    transactions.filter(
      (transaction) =>
        ![
          "stop_contact",
          "stop_retries",
          "human_review",
        ].includes(transaction.recommended_action),
    );

  const actionableRevenue =
    actionableTransactions.reduce(
      (total, transaction) =>
        total + Number(transaction.amount || 0),
      0,
    );

  const failureCounts = transactions.reduce(
    (counts, transaction) => {
      const failureCode =
        transaction.failure_code || "unknown";

      counts[failureCode] =
        (counts[failureCode] || 0) + 1;

      return counts;
    },
    {},
  );

  const topFailureEntry = Object.entries(
    failureCounts,
  ).sort(
    (first, second) => second[1] - first[1],
  )[0];

  const topFailure = topFailureEntry
    ? formatAction(topFailureEntry[0])
    : "No data";

  const exportReport = () => {
    if (transactions.length === 0) {
      return;
    }

    const headings = [
      "Transaction ID",
      "Payment ID",
      "Customer",
      "Email",
      "Amount",
      "Currency",
      "Failure Code",
      "Risk Score",
      "Recommended Action",
      "Status",
      "Approval Status",
      "Recovered Amount",
      "Created At",
    ];

    const rows = transactions.map(
      (transaction) => [
        transaction.id,
        transaction.payment_id,
        transaction.customer_name,
        transaction.customer_email,
        transaction.amount,
        transaction.currency,
        transaction.failure_code,
        transaction.risk_score,
        transaction.recommended_action,
        transaction.status,
        transaction.approval_status,
        transaction.recovered_amount,
        transaction.created_at,
      ],
    );

    const csvContent = [
      headings.map(escapeCSV).join(","),
      ...rows.map((row) =>
        row.map(escapeCSV).join(","),
      ),
    ].join("\n");

    const csvBlob = new Blob([csvContent], {
      type: "text/csv;charset=utf-8",
    });

    const downloadURL =
      URL.createObjectURL(csvBlob);

    const downloadLink =
      document.createElement("a");

    downloadLink.href = downloadURL;
    downloadLink.download =
      `revivepay-report-${
        new Date().toISOString().split("T")[0]
      }.csv`;

    document.body.appendChild(downloadLink);
    downloadLink.click();
    downloadLink.remove();

    URL.revokeObjectURL(downloadURL);
  };

  const insights = [
    {
      label: "Actionable revenue",
      value: new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(actionableRevenue),
      description:
        "Value eligible for safe recovery actions",
      icon: TrendingUp,
      color: "green",
    },
    {
      label: "Top failure",
      value: topFailure,
      description:
        topFailureEntry
          ? `${topFailureEntry[1]} affected transactions`
          : "Upload transactions to analyse",
      icon: Sparkles,
      color: "purple",
    },
    {
      label: "High-risk cases",
      value: highRiskTransactions.length,
      description:
        "Transactions with risk score of 65% or above",
      icon: AlertTriangle,
      color: "orange",
    },
    {
      label: "Safety protected",
      value: safetyProtectedTransactions.length,
      description:
        "Unsafe contact or retries prevented",
      icon: ShieldCheck,
      color: "blue",
    },
  ];

  return (
    <section
      className="executive-insights"
      id="insights"
    >
      <div className="insights-heading">
        <div>
          <p className="eyebrow">
            Decision intelligence
          </p>

          <h3>Executive Recovery Insights</h3>

          <p>
            A concise view of recovery opportunity,
            risk and safety controls.
          </p>
        </div>

        <button
          className="export-report-button"
          onClick={exportReport}
          disabled={transactions.length === 0}
        >
          <Download size={17} />
          Export CSV Report
        </button>
      </div>

      <div className="insights-grid">
        {insights.map((insight) => {
          const Icon = insight.icon;

          return (
            <article
              className="insight-card"
              key={insight.label}
            >
              <div
                className={`insight-icon ${insight.color}`}
              >
                <Icon size={20} />
              </div>

              <div>
                <span>{insight.label}</span>
                <strong>{insight.value}</strong>
                <p>{insight.description}</p>
              </div>
            </article>
          );
        })}
      </div>

      {humanReviewTransactions.length > 0 && (
        <div className="review-insight">
          <ShieldCheck size={20} />

          <div>
            <strong>
              {humanReviewTransactions.length} transaction
              {humanReviewTransactions.length === 1
                ? ""
                : "s"}{" "}
              need human attention
            </strong>

            <p>
              RevivePay has paused automatic execution for
              uncertain or high-risk recovery decisions.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

export default ExecutiveInsights;