import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AlertTriangle,
  CheckCircle2,
  Database,
  IndianRupee,
  RefreshCw,
  Search,
  ShieldCheck,
  Upload,
} from "lucide-react";
import AIWorkbench from "./components/AIWorkbench";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import toast, { Toaster } from "react-hot-toast";
import apiClient from "./api/client";
import "./App.css";

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatAction(action) {
  if (!action) {
    return "Not available";
  }

  return action
    .split("_")
    .map(
      (word) =>
        word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

function App() {
  const fileInputRef = useRef(null);

  const [metrics, setMetrics] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [selectedTransaction, setSelectedTransaction] =
    useState(null);
  const [messagePreview, setMessagePreview] =
    useState(null);

  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] =
    useState("all");

  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [approvingId, setApprovingId] = useState(null);
  const [previewLoading, setPreviewLoading] =
    useState(false);

  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] =
    useState("");

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [metricsResponse, transactionsResponse] =
        await Promise.all([
          apiClient.get("/metrics"),
          apiClient.get("/transactions"),
        ]);

      setMetrics(metricsResponse.data);
      setTransactions(transactionsResponse.data);

      setSelectedTransaction((currentTransaction) => {
        if (!currentTransaction) {
          return null;
        }

        return (
          transactionsResponse.data.find(
            (transaction) =>
              transaction.id === currentTransaction.id,
          ) || null
        );
      });
    } catch (requestError) {
      console.error(requestError);

      setError(
        "Could not connect to the backend. Confirm that FastAPI is running on port 8000.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);
  useEffect(() => {
  if (!error) {
    return;
  }

  toast.error(error, {
    id: "application-error",
  });
}, [error]);

useEffect(() => {
  if (!successMessage) {
    return;
  }

  toast.success(successMessage, {
    id: "application-success",
  });
}, [successMessage]);

  const loadDemoData = async () => {
    try {
      setLoadingDemo(true);
      setError("");
      setSuccessMessage("");
      const toastId = toast.loading(
  "Loading demonstration transactions...",
);

      const csvResponse = await fetch(
        "/demo_transactions.csv",
      );

      if (!csvResponse.ok) {
        throw new Error(
          "The demonstration CSV could not be loaded.",
        );
      }

      const csvBlob = await csvResponse.blob();
      const demoFile = new File(
        [csvBlob],
        "demo_transactions.csv",
        { type: "text/csv" },
      );

      const formData = new FormData();
      formData.append("file", demoFile);

      const response = await apiClient.post(
  "/transactions/upload-csv",
  formData,
  {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  },
);

      const result = response.data;
      toast.dismiss(toastId);

      setSuccessMessage(
        result.imported_rows > 0
          ? `${result.imported_rows} demonstration transactions loaded successfully.`
          : "Demo data is already loaded. The dashboard has been refreshed.",
      );

      await loadDashboard();
    } catch (demoError) {
      toast.dismiss(toastId);
  console.error(
    "Demo data loading error:",
    demoError.response?.data || demoError,
  );

  const responseDetail =
    demoError.response?.data?.detail;

  let errorMessage =
    "The demonstration data could not be loaded.";

  if (typeof responseDetail === "string") {
    errorMessage = responseDetail;
  } else if (Array.isArray(responseDetail)) {
    errorMessage = responseDetail
      .map((item) => {
        const location = Array.isArray(item.loc)
          ? item.loc.join(" → ")
          : "request";

        return `${location}: ${item.msg}`;
      })
      .join(", ");
  } else if (demoError.message) {
    errorMessage = demoError.message;
  }

  setError(errorMessage);
} finally {
  setLoadingDemo(false);
}
  };

  const uploadCSV = async (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please select a valid CSV file.");
      event.target.value = "";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploading(true);
      setError("");
      setSuccessMessage("");

      const response = await apiClient.post(
        "/transactions/upload-csv",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        },
      );

      const result = response.data;

      setSuccessMessage(
        `${result.imported_rows} transactions imported successfully. ` +
          `${result.rejected_rows} rows rejected.`,
      );

      await loadDashboard();
    } catch (uploadError) {
      console.error(uploadError);

      const detail =
        uploadError.response?.data?.detail ||
        "The CSV file could not be uploaded.";

      setError(
        typeof detail === "string"
          ? detail
          : "The CSV file contains invalid data.",
      );
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const approveTransaction = async (transaction) => {
    const blockedActions = [
      "stop_contact",
      "stop_retries",
    ];

    if (
      blockedActions.includes(
        transaction.recommended_action,
      )
    ) {
      setError(
        "This recovery action is blocked by the safety policy.",
      );
      return;
    }

    const confirmed = window.confirm(
      `Approve "${formatAction(
        transaction.recommended_action,
      )}" for ${transaction.customer_name}?`,
    );

    if (!confirmed) {
      return;
    }

    try {
      setApprovingId(transaction.id);
      setError("");
      setSuccessMessage("");

      const idempotencyKey = [
        "frontend",
        transaction.id,
        Date.now(),
        crypto.randomUUID(),
      ].join("-");

      const response = await apiClient.post(
        `/transactions/${transaction.id}/approve`,
        {
          approved_by: "Mishthi",
          idempotency_key: idempotencyKey,
        },
      );

      setSuccessMessage(response.data.message);
      await loadDashboard();
    } catch (approvalError) {
      console.error(approvalError);

      const detail =
        approvalError.response?.data?.detail ||
        "The recovery action could not be approved.";

      setError(
        typeof detail === "string"
          ? detail
          : "The recovery action could not be approved.",
      );
    } finally {
      setApprovingId(null);
    }
  };

  const previewMessage = async (
    transaction,
    language,
  ) => {
    const blockedActions = [
      "stop_contact",
      "stop_retries",
    ];

    if (
      blockedActions.includes(
        transaction.recommended_action,
      )
    ) {
      setError("");

      setMessagePreview({
        allowed: false,
        blocked_reason:
          "The safety policy does not permit customer communication for this transaction.",
      });

      return;
    }

    try {
      setPreviewLoading(true);
      setError("");
      setMessagePreview(null);

      const response = await apiClient.post(
        `/transactions/${transaction.id}/message-preview`,
        {
          language,
          requested_by: "Mishthi",
        },
      );

      setMessagePreview(response.data);
    } catch (previewError) {
      console.error(
        "Message preview error:",
        previewError.response?.status,
        previewError.response?.data,
      );

      const responseDetail =
        previewError.response?.data?.detail;

      let errorMessage =
        "The recovery message could not be generated.";

      if (typeof responseDetail === "string") {
        errorMessage = responseDetail;
      } else if (Array.isArray(responseDetail)) {
        errorMessage = responseDetail
          .map((item) => item.msg)
          .join(", ");
      }

      setError(errorMessage);
    } finally {
      setPreviewLoading(false);
    }
  };

  const openTransactionDetails = (transaction) => {
    setSelectedTransaction(transaction);
    setMessagePreview(null);
    setError("");
    setSuccessMessage("");
  };

  const closeTransactionDetails = () => {
    setSelectedTransaction(null);
    setMessagePreview(null);
    setError("");
  };

  const filteredTransactions = transactions.filter(
    (transaction) => {
      const searchValue = searchTerm
        .trim()
        .toLowerCase();

      const matchesSearch =
        !searchValue ||
        transaction.payment_id
          ?.toLowerCase()
          .includes(searchValue) ||
        transaction.customer_name
          ?.toLowerCase()
          .includes(searchValue) ||
        transaction.customer_email
          ?.toLowerCase()
          .includes(searchValue) ||
        transaction.failure_code
          ?.toLowerCase()
          .includes(searchValue) ||
        transaction.recommended_action
          ?.toLowerCase()
          .includes(searchValue);

      const matchesStatus =
        statusFilter === "all" ||
        transaction.status === statusFilter;

      return matchesSearch && matchesStatus;
    },
  );
  const allAuditEvents = transactions
    .flatMap((transaction) =>
      (transaction.audits || []).map((audit) => ({
        ...audit,
        transaction_id: transaction.id,
        payment_id: transaction.payment_id,
        customer_name: transaction.customer_name,
      })),
    )
    .sort(
      (firstAudit, secondAudit) =>
        new Date(secondAudit.created_at) -
        new Date(firstAudit.created_at),
    );

  const scrollToSection = (sectionId) => {
    const section = document.getElementById(sectionId);

    section?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  const metricCards = [
    {
      title: "Revenue at risk",
      value: formatCurrency(
        metrics?.total_revenue_at_risk,
      ),
      icon: IndianRupee,
      color: "orange",
    },
    {
      title: "Recovered revenue",
      value: formatCurrency(metrics?.recovered_revenue),
      icon: CheckCircle2,
      color: "green",
    },
    {
      title: "Recovery rate",
      value: `${metrics?.recovery_rate || 0}%`,
      icon: RefreshCw,
      color: "blue",
    },
    {
      title: "Safety stops",
      value: metrics?.safety_stops || 0,
      icon: ShieldCheck,
      color: "purple",
    },
  ];

  return (
     <>
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 4500,
        style: {
          maxWidth: "420px",
          padding: "14px 16px",
          border: "1px solid #e2e8f0",
          borderRadius: "13px",
          background: "#ffffff",
          color: "#172033",
          boxShadow:
            "0 15px 35px rgba(15, 23, 42, 0.15)",
          fontSize: "14px",
          fontWeight: 600,
        },
        success: {
          iconTheme: {
            primary: "#059669",
            secondary: "#ffffff",
          },
        },
        error: {
          iconTheme: {
            primary: "#dc2626",
            secondary: "#ffffff",
          },
        },
      }}
    />
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">R</div>

          <div>
            <h1>RevivePay AI</h1>
            <span>Recovery intelligence</span>
          </div>
        </div>

        <nav>
          <button
            className="nav-item active"
            onClick={() => scrollToSection("dashboard")}
          >
            Dashboard
          </button>
          <button
            className="nav-item"
            onClick={() => scrollToSection("ai-workbench")}
          >
            AI Workbench
          </button>

          <button
            className="nav-item"
            onClick={() => scrollToSection("analytics")}
          >
            Analytics
          </button>

          <button
            className="nav-item"
            onClick={() => scrollToSection("transactions")}
          >
            Transactions
          </button>

          <button
            className="nav-item"
            onClick={() => scrollToSection("audit-history")}
          >
            Audit history
          </button>
        </nav>

        <div className="safety-card">
          <ShieldCheck size={22} />

          <div>
            <strong>Human controlled</strong>
            <p>Recovery actions require approval.</p>
          </div>
        </div>
      </aside>

      <main className="main-content" id="dashboard">
        <header className="page-header">
          <div>
            <p className="eyebrow">
              Payment recovery dashboard
            </p>

            <h2>Revenue Recovery Overview</h2>

            <p>
              Diagnose failed payments and execute safe
              recovery actions.
            </p>
          </div>

          <div className="header-actions">
            <button
              className="demo-button"
              onClick={loadDemoData}
              disabled={loadingDemo || uploading}
            >
              <Database
                size={17}
                className={loadingDemo ? "spinning" : ""}
              />

              {loadingDemo
                ? "Loading demo..."
                : "Load Demo Data"}
            </button>

            <button
              className="secondary-button"
              onClick={loadDashboard}
              disabled={loading}
            >
              <RefreshCw
                size={17}
                className={loading ? "spinning" : ""}
              />

              Refresh
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              hidden
              onChange={uploadCSV}
            />

            <button
              className="primary-button"
              onClick={() =>
                fileInputRef.current?.click()
              }
              disabled={uploading}
            >
              <Upload size={17} />

              {uploading ? "Uploading..." : "Upload CSV"}
            </button>
          </div>
        </header>

        

        

        <section className="metrics-grid">
          {metricCards.map((card) => {
            const Icon = card.icon;

            return (
              <article
                className="metric-card"
                key={card.title}
              >
                <div
                  className={`metric-icon ${card.color}`}
                >
                  <Icon size={21} />
                </div>

                <div>
                  <p>{card.title}</p>

                  <strong>
                    {loading ? "Loading..." : card.value}
                  </strong>
                </div>
              </article>
            );
          })}
        </section>

        <AIWorkbench />

        <AnalyticsDashboard transactions={transactions} />

        <section className="table-card" id="transactions">
          <div className="section-heading">
            <div>
              <h3>Recent failed transactions</h3>

              <p>
                AI recommendations and payment recovery
                status
              </p>
            </div>

            <span className="record-count">
              {filteredTransactions.length} records
            </span>
          </div>

          <div className="table-filters">
            <label className="search-box">
              <Search size={17} />

              <input
                type="search"
                placeholder="Search payment, customer or failure..."
                value={searchTerm}
                onChange={(event) =>
                  setSearchTerm(event.target.value)
                }
              />
            </label>

            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value)
              }
            >
              <option value="all">All statuses</option>
              <option value="diagnosed">
                Diagnosed
              </option>
              <option value="awaiting_customer_consent">
                Awaiting customer consent
              </option>
              <option value="payment_link_created">
                Payment link created
              </option>
              <option value="escalated">
                Escalated
              </option>
              <option value="execution_failed">
                Execution failed
              </option>
              <option value="recovered">
                Recovered
              </option>
            </select>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Payment</th>
                  <th>Customer</th>
                  <th>Amount</th>
                  <th>Failure</th>
                  <th>Recommendation</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {!loading &&
                  filteredTransactions.length === 0 && (
                    <tr>
                      <td
                        colSpan="7"
                        className="empty-state"
                      >
                        {transactions.length === 0
                          ? "No transactions found. Upload the sample CSV."
                          : "No transactions match your search or filter."}
                      </td>
                    </tr>
                  )}

                {filteredTransactions
                  .slice(0, 10)
                  .map((transaction) => {
                    const safetyBlocked = [
                      "stop_contact",
                      "stop_retries",
                    ].includes(
                      transaction.recommended_action,
                    );

                    return (
                      <tr key={transaction.id}>
                        <td>
                          <strong>
                            {transaction.payment_id}
                          </strong>

                          <span className="subtext">
                            ID: {transaction.id}
                          </span>
                        </td>

                        <td>
                          {transaction.customer_name}

                          <span className="subtext">
                            {transaction.customer_email}
                          </span>
                        </td>

                        <td className="amount">
                          {formatCurrency(
                            transaction.amount,
                          )}
                        </td>

                        <td>
                          {formatAction(
                            transaction.failure_code,
                          )}
                        </td>

                        <td>
                          <span className="action-badge">
                            {formatAction(
                              transaction.recommended_action,
                            )}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`status-badge ${transaction.status}`}
                          >
                            {formatAction(
                              transaction.status,
                            )}
                          </span>
                        </td>

                        <td>
                          <div className="table-actions">
                            <button
                              className="details-button"
                              onClick={() =>
                                openTransactionDetails(
                                  transaction,
                                )
                              }
                            >
                              View details
                            </button>

                            {safetyBlocked ? (
                              <button
                                className="blocked-button"
                                disabled
                              >
                                Safety blocked
                              </button>
                            ) : transaction.status ===
                              "recovered" ? (
                              <button
                                className="completed-button"
                                disabled
                              >
                                Recovered
                              </button>
                            ) : (
                              <button
                                className="approve-button"
                                onClick={() =>
                                  approveTransaction(
                                    transaction,
                                  )
                                }
                                disabled={
                                  approvingId ===
                                  transaction.id
                                }
                              >
                                {approvingId ===
                                transaction.id
                                  ? "Approving..."
                                  : "Review & approve"}
                              </button>

                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>

        <section
          className="audit-history-card"
          id="audit-history"
        >
          <div className="section-heading">
            <div>
              <h3>System audit history</h3>
              <p>
                Chronological record of diagnoses,
                approvals, safety decisions, and recovery
                actions
              </p>
            </div>

            <span className="record-count">
              {allAuditEvents.length} events
            </span>
          </div>

          <div className="central-audit-list">
            {allAuditEvents.length === 0 ? (
              <p className="empty-state">
                No audit events are available.
              </p>
            ) : (
              allAuditEvents.slice(0, 20).map((audit) => (
                <article
                  className="central-audit-item"
                  key={`${audit.transaction_id}-${audit.id}`}
                >
                  <div className="audit-event-icon">
                    <ShieldCheck size={17} />
                  </div>

                  <div className="central-audit-content">
                    <div className="central-audit-title">
                      <strong>
                        {formatAction(audit.event_type)}
                      </strong>

                      <span>
                        {new Date(
                          audit.created_at,
                        ).toLocaleString("en-IN")}
                      </span>
                    </div>

                    <p>{audit.details}</p>

                    <div className="audit-metadata">
                      <span>
                        Payment: {audit.payment_id}
                      </span>
                      <span>
                        Customer: {audit.customer_name}
                      </span>
                      <span>Actor: {audit.actor}</span>
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </main>

      {selectedTransaction && (
        <div
          className="modal-backdrop"
          onClick={closeTransactionDetails}
        >
          <section
            className="transaction-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <p className="eyebrow">
                  Transaction details
                </p>

                <h3>
                  {selectedTransaction.payment_id}
                </h3>
              </div>

              <button
                className="close-button"
                onClick={closeTransactionDetails}
                aria-label="Close transaction details"
              >
                ×
              </button>
            </div>

            <div className="detail-grid">
              <div>
                <span>Customer</span>

                <strong>
                  {selectedTransaction.customer_name}
                </strong>

                <small>
                  {selectedTransaction.customer_email}
                </small>
              </div>

              <div>
                <span>Amount</span>

                <strong>
                  {formatCurrency(
                    selectedTransaction.amount,
                  )}
                </strong>
              </div>

              <div>
                <span>Status</span>

                <strong>
                  {formatAction(
                    selectedTransaction.status,
                  )}
                </strong>
              </div>

              <div>
                <span>Risk score</span>

                <strong>
                  {Math.round(
                    selectedTransaction.risk_score * 100,
                  )}
                  %
                </strong>
              </div>
            </div>

            <div className="recommendation-panel">
              <span>AI recommendation</span>

              <h4>
                {formatAction(
                  selectedTransaction.recommended_action,
                )}
              </h4>

              <p>
                {
                  selectedTransaction.recommendation_reason
                }
              </p>
            </div>

            {["stop_contact", "stop_retries"].includes(
              selectedTransaction.recommended_action,
            ) ? (
              <div className="message-preview-section">
                <div className="message-result blocked">
                  <strong>
                    Customer communication blocked
                  </strong>

                  <p>
                    The safety policy does not permit
                    recovery-message generation for this
                    transaction.
                  </p>
                </div>
              </div>
            ) : (
              <div className="message-preview-section">
                <div className="message-preview-heading">
                  <div>
                    <span>Customer communication</span>
                    <h4>Recovery message preview</h4>
                  </div>

                  <div className="language-buttons">
                    <button
                      onClick={() =>
                        previewMessage(
                          selectedTransaction,
                          "english",
                        )
                      }
                      disabled={previewLoading}
                    >
                      English
                    </button>

                    <button
                      onClick={() =>
                        previewMessage(
                          selectedTransaction,
                          "hindi",
                        )
                      }
                      disabled={previewLoading}
                    >
                      Hindi
                    </button>
                  </div>
                </div>

                {previewLoading && (
                  <p className="preview-placeholder">
                    Generating a safe message preview...
                  </p>
                )}

                {!previewLoading && !messagePreview && (
                  <p className="preview-placeholder">
                    Select a language to generate a message.
                    This does not send anything to the
                    customer.
                  </p>
                )}

                {messagePreview && (
                  <div
                    className={`message-result ${
                      messagePreview.allowed
                        ? "allowed"
                        : "blocked"
                    }`}
                  >
                    {messagePreview.allowed ? (
                      <>
                        <p className="generated-message">
                          {messagePreview.message}
                        </p>

                        <div className="preview-flags">
                          <span>
                            Language:{" "}
                            {formatAction(
                              messagePreview.language,
                            )}
                          </span>

                          <span>
                            Human approval:{" "}
                            {messagePreview
                              .requires_human_approval
                              ? "Required"
                              : "Not required"}
                          </span>

                          {messagePreview.used_fallback && (
                            <span>
                              Safety fallback used
                            </span>
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <strong>
                          Message generation blocked
                        </strong>

                        <p>
                          {messagePreview.blocked_reason}
                        </p>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            {selectedTransaction.provider_url && (
              <div className="payment-link-panel">
                <div>
                  <span>Payment link created</span>

                  <strong>
                    {
                      selectedTransaction.provider_reference
                    }
                  </strong>
                </div>

                <a
                  href={selectedTransaction.provider_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open payment link
                </a>
              </div>
            )}

            <div className="audit-section">
              <h4>Audit history</h4>

              {selectedTransaction.audits?.length ? (
                <div className="audit-list">
                  {selectedTransaction.audits.map(
                    (audit) => (
                      <article
                        className="audit-item"
                        key={audit.id}
                      >
                        <div className="audit-dot" />

                        <div>
                          <strong>
                            {formatAction(
                              audit.event_type,
                            )}
                          </strong>

                          <p>{audit.details}</p>

                          <small>
                            {audit.actor} ·{" "}
                            {new Date(
                              audit.created_at,
                            ).toLocaleString("en-IN")}
                          </small>
                        </div>
                      </article>
                    ),
                  )}
                </div>
              ) : (
                <p className="empty-audit">
                  No audit events are available.
                </p>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
    </>
  );
}

export default App;
