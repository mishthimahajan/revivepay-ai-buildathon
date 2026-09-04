import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = [
  "#6558f5",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
  "#0ea5e9",
  "#8b5cf6",
];

function formatLabel(value) {
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

function AnalyticsDashboard({ transactions }) {
  const failureData = useMemo(() => {
    const counts = {};

    transactions.forEach((transaction) => {
      const key =
        transaction.failure_code || "unknown";

      counts[key] = (counts[key] || 0) + 1;
    });

    return Object.entries(counts)
      .map(([failure, count]) => ({
        name: formatLabel(failure),
        count,
      }))
      .sort((first, second) => second.count - first.count);
  }, [transactions]);

  const statusData = useMemo(() => {
    const counts = {};

    transactions.forEach((transaction) => {
      const key = transaction.status || "unknown";

      counts[key] = (counts[key] || 0) + 1;
    });

    return Object.entries(counts).map(
      ([status, value]) => ({
        name: formatLabel(status),
        value,
      }),
    );
  }, [transactions]);

  return (
    <section
      className="analytics-section"
      id="analytics"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Recovery intelligence</p>
          <h3>Failure and Recovery Analytics</h3>
          <p>
            Visual breakdown of payment failures and
            transaction outcomes.
          </p>
        </div>

        <span className="record-count">
          {transactions.length} analysed
        </span>
      </div>

      {transactions.length === 0 ? (
        <div className="analytics-empty">
          Upload the sample CSV to generate analytics.
        </div>
      ) : (
        <div className="analytics-grid">
          <article className="chart-card">
            <div className="chart-heading">
              <h4>Failure categories</h4>
              <span>Number of transactions</span>
            </div>

            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={failureData}
                  margin={{
                    top: 10,
                    right: 10,
                    left: -20,
                    bottom: 40,
                  }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="#e2e8f0"
                  />

                  <XAxis
                    dataKey="name"
                    angle={-25}
                    textAnchor="end"
                    interval={0}
                    height={75}
                    tick={{
                      fill: "#64748b",
                      fontSize: 11,
                    }}
                  />

                  <YAxis
                    allowDecimals={false}
                    tick={{
                      fill: "#64748b",
                      fontSize: 12,
                    }}
                  />

                  <Tooltip
                    cursor={{
                      fill: "rgba(101, 88, 245, 0.06)",
                    }}
                  />

                  <Bar
                    dataKey="count"
                    name="Transactions"
                    fill="#6558f5"
                    radius={[7, 7, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article className="chart-card">
            <div className="chart-heading">
              <h4>Transaction status</h4>
              <span>Recovery workflow distribution</span>
            </div>

            <div className="chart-container">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <PieChart>
                  <Pie
                    data={statusData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="45%"
                    innerRadius={58}
                    outerRadius={92}
                    paddingAngle={3}
                  >
                    {statusData.map((entry, index) => (
                      <Cell
                        key={entry.name}
                        fill={
                          COLORS[index % COLORS.length]
                        }
                      />
                    ))}
                  </Pie>

                  <Tooltip />
                  <Legend verticalAlign="bottom" />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </article>
        </div>
      )}
    </section>
  );
}

export default AnalyticsDashboard;