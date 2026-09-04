RevivePay AI

An explainable, human-controlled payment recovery platform that diagnoses failed payments, recommends safe recovery actions, and preserves a complete audit trail.

Live Application

Frontend: https://revivepay-ai-buildathon.vercel.app

Backend API: https://revivepay-ai-buildathon.onrender.com

Swagger documentation: https://revivepay-ai-buildathon.onrender.com/docs

Replace these placeholder URLs with the real Vercel and Render URLs before submitting the project.

Problem Statement

Legitimate payments fail for many reasons, including insufficient funds, expired cards, bank downtime, network problems, and provider errors. Treating every failure with the same retry strategy can frustrate customers, waste operational effort, and create consent or compliance risks.

RevivePay AI turns each failed payment into a controlled recovery workflow. It combines machine-learning classification with deterministic safety rules and human approval before execution.

Key Features

Interactive dashboard for revenue at risk, recovered revenue, recovery rate, and safety stops

CSV ingestion with validation, duplicate detection, and row-level rejection reporting

Explainable AI workbench for classifying natural-language payment failure descriptions

Confidence score and automatic human-review escalation for uncertain predictions

Policy-based recommendations such as payment link, retry stop, consent request, or human review

Consent, do-not-contact, retry-limit, and risk-score safety checks

Human approval before recovery execution

Idempotency protection against repeated approvals

Razorpay Payment Link integration with a safe mock demonstration mode

HMAC-verified Razorpay webhook processing

English and Hinglish recovery-message previews

Searchable transaction history and chronological audit trail

Demo-data loading and mock-mode data clearing

Responsive React interface with analytics and clear operational states

How It Works

flowchart TD
    A[Failed payment] --> B[API or CSV validation]
    B --> C[AI failure classification]
    C --> D[Safety policy engine]
    D --> E{Safe and confident?}
    E -- No --> F[Human review or safety stop]
    E -- Yes --> G[Operator approval]
    G --> H[Mock or Razorpay execution]
    H --> I[Signed webhook confirmation]
    F --> J[Audit trail]
    I --> J

Safety-First Design

RevivePay AI does not allow the model to directly perform a financial action. The classifier interprets the failure, while deterministic application rules decide whether an action is permitted.

The system blocks or escalates a case when:

the customer has opted out of contact;

customer consent is missing;

the retry limit has been reached;

the risk score exceeds the allowed threshold;

the failure type is unknown; or

model confidence is below the safety threshold.

Every important state change is stored in the audit history with its actor, timestamp, event type, and explanation.

Technology Stack

Layer

Technologies

Frontend

React, Vite, Axios, Lucide React, Recharts

Backend

Python, FastAPI, Pydantic, SQLAlchemy

Machine learning

scikit-learn, text vectorization, Logistic Regression, Joblib

Database

SQLite locally; PostgreSQL recommended for production

Payment integration

Razorpay Payment Links and signed webhooks

Testing

Pytest, FastAPI TestClient

Deployment

Vercel frontend, Render backend

Project Structure

revivepay-ai-buildathon/
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── csv_importer.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── message_generator.py
│   │   ├── ml_classifier.py
│   │   ├── models.py
│   │   ├── payment_provider.py
│   │   ├── recovery_engine.py
│   │   ├── schemas.py
│   │   └── webhook_service.py
│   ├── artifacts/
│   │   └── failure_classifier.joblib
│   ├── tests/
│   ├── requirements.txt
│   └── train_classifier.py
├── data/
│   ├── failure_training.csv
│   └── sample_transactions.csv
└── frontend/
    ├── src/
    │   ├── api/client.js
    │   ├── components/
    │   ├── App.jsx
    │   └── App.css
    ├── package.json
    └── vite.config.js

Local Setup

Prerequisites

Python 3.11

Node.js 20 or newer

Git

1. Clone the repository

git clone https://github.com/mishthimahajan/revivepay-ai-buildathon.git
cd revivepay-ai-buildathon

2. Start the backend

On Windows PowerShell:

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

Backend URLs:

Health: http://127.0.0.1:8000/health

Swagger: http://127.0.0.1:8000/docs

3. Start the frontend

Open a second terminal:

cd frontend
npm install
npm run dev

Open http://localhost:5173.

Environment Variables

Create backend/.env:

DATABASE_URL=sqlite:///./revivepay.db
FRONTEND_ORIGIN=http://localhost:5173
PROVIDER_MODE=mock
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=replace_with_a_private_random_secret

Create frontend/.env.local:

VITE_API_BASE_URL=http://127.0.0.1:8000

Never commit .env, .env.local, provider credentials, or production secrets.

API Overview

Method

Endpoint

Purpose

GET

/health

Service and ML-model health

GET

/metrics

Dashboard metrics

GET

/transactions

List transactions

POST

/transactions

Diagnose one transaction

POST

/transactions/upload-csv

Validate and import CSV data

GET

/transactions/{transaction_id}

Get transaction details

POST

/transactions/{transaction_id}/approve

Approve a recovery action

POST

/transactions/{transaction_id}/message-preview

Generate a safe message preview

POST

/ai/classify-failure

Classify a failure description

POST

/webhooks/razorpay

Process a signed Razorpay webhook

The interactive and authoritative endpoint schemas are available at /docs.

CSV Format

Use data/sample_transactions.csv as the reference. Each payment_id must be unique. The importer validates the input and reports rejected rows without silently accepting malformed data.

Running Tests

From the backend directory:

python -m pytest -v

The test suite covers recovery policies, classification behavior, message generation, CSV processing, approval safety, and webhook verification.

Deployment

Backend on Render

Root directory: backend

Build command: pip install -r requirements.txt

Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT

Python version: 3.11

Configure DATABASE_URL, FRONTEND_ORIGIN, PROVIDER_MODE, and any Razorpay secrets in Render's environment settings.

Use managed PostgreSQL for persistent production data.

Frontend on Vercel

Root directory: frontend

Framework: Vite

Build command: npm run build

Output directory: dist

Set VITE_API_BASE_URL to the deployed Render backend URL.

After Vercel provides the final domain, set the same exact origin as FRONTEND_ORIGIN on Render and redeploy the backend.

Demonstration Flow

Load the demo data or upload data/sample_transactions.csv.

Review dashboard metrics and analytics.

Use the AI Workbench to classify a failure description.

Open a transaction to inspect the recommendation and explanation.

Compare an eligible recovery with a safety-blocked transaction.

Approve an eligible action in mock mode.

Inspect the complete audit timeline.

Current Limitations and Roadmap

Replace the prototype schema creation flow with Alembic migrations.

Add authentication and role-based permissions for operators and administrators.

Add background workers for long-running provider and notification tasks.

Train and evaluate the classifier on a larger, representative dataset.

Add model monitoring, drift detection, and structured evaluation metrics.

Support additional payment providers and communication channels.

Add rate limiting, observability, and production alerting.

Responsible AI Statement

The classifier is decision support, not an autonomous financial authority. Low-confidence predictions are escalated, deterministic policies protect consent and retry limits, sensitive actions require approval, and audit records preserve accountability.

Author

Mishthi Mahajan
B.Tech Computer Science Engineering, 2023–2027
Full-Stack Developer focused on MERN, Python, AI/ML integration, and reliable backend systems.

GitHub: mishthimahajan

LinkedIn: https://www.linkedin.com/in/mishthi-mahajan

License

This project is intended for educational, portfolio, and demonstration purposes. Add a license before permitting external reuse.
