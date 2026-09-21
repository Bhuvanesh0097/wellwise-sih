# WellWise — AI-Powered Baghewala Digital Twin

WellWise is an AI-enabled **well-to-surface Digital Twin** prototype for optimizing **Cyclic Steam Stimulation (CSS)** and **Sucker Rod Pump (SRP)** operations in heavy-oil wells of the Baghewala Field.

**Workflow:** MONITOR → PREDICT → SIMULATE → OPTIMIZE → ENGINEER DECISION

> **Prototype scope:** The current demonstration uses synthetic/simulated Baghewala well data. WellWise is an engineer-controlled decision-support prototype and does not perform autonomous field control.

## Overview

WellWise creates a unified view of the:

**Reservoir → Wellbore → SRP → Surface**

The platform combines operational telemetry, machine-learning prediction, What-If simulation, optimization, and engineer review in a single workflow.

### AI Models

- **Model 1:** Future reservoir temperature
- **Model 2:** Future oil rate
- **Model 3:** Rod-floating risk

## CSS Parameters

- Steam rate
- Steam temperature
- Injection pressure
- Injection duration
- Soak time

## SRP Parameters

- Stroke length
- Strokes per minute (SPM)
- VFD frequency

## Key Features

### 1. Digital Twin

Provides a unified representation of the well-to-surface system using current telemetry and static well parameters.

### 2. 24-Hour AI Prediction

Predicts:

- Reservoir temperature
- Future oil production rate
- Rod-floating probability/risk

### 3. What-If Simulation

Engineers can change CSS and SRP parameters and compare predicted outcomes without automatically applying changes.

### 4. CSS + SRP Optimization

The current **WellWise Optimizer V2.1 FAST** evaluates candidate operating combinations, filters scenarios using operating constraints, and produces a recommendation for engineer review.

### 5. Engineer Review

Every recommendation remains human-in-the-loop:

- **Approve** — accept the recommendation
- **Modify** — change parameters and re-simulate
- **Reject** — record a rejection reason

### 6. Historical Trends

Displays simulated telemetry history for production, temperature, pressure, energy, SPM, and pump fillage.

### 7. Decision History

Stores engineer approvals, modifications, and rejections for later review.

---

## System Architecture

```text
Simulated Telemetry
        ↓
Supabase PostgreSQL
        ↓
React Frontend
        ↓
FastAPI Backend
        ↓
Preprocessing
        ↓
┌───────────────────────────────────┐
│ Model 1 → Reservoir Temperature   │
│ Model 2 → Future Oil Rate         │
│ Model 3 → Rod-Floating Risk       │
└───────────────────────────────────┘
        ↓
Digital Twin Prediction
        ↓
What-If Simulation
        ↓
CSS + SRP Optimization
        ↓
AI Recommendation
        ↓
Engineer Review
   ┌────┼─────┐
Approve Modify Reject
        ↓
Decision History
Technology Stack
Layer	Technology
Frontend	React + TypeScript + Vite
Backend	FastAPI + Python
Machine Learning	XGBoost
Data Storage	PostgreSQL / Supabase
Authentication Concept	Supabase Auth
Database Security	PostgreSQL Row Level Security
Simulation	Python + FastAPI
Optimization	WellWise Optimizer V2.1 FAST
Deployment	Render
Version Control	GitHub
API Endpoints
GET  /api/health
GET  /api/wells
GET  /api/telemetry/{well_id}
GET  /api/telemetry-history/{well_id}
GET  /api/predict/{well_id}
GET  /api/digital-twin/{well_id}
GET  /api/simulate/{well_id}
POST /api/what-if/{well_id}
GET  /api/optimize/{well_id}
POST /api/decisions/{well_id}
GET  /api/decisions/history/{well_id}
Machine Learning Performance
Model 1 — Reservoir Temperature
MAE: ~4.48 °C
RMSE: ~5.52 °C
R²: ~0.65
Model 2 — Future Oil Rate
MAE: ~7.32 BOPD
RMSE: ~9.98
R²: ~0.81
Model 3 — Rod-Floating Risk

Prototype test performance at the configured threshold:

Accuracy: ~0.54
Precision: ~0.26
Recall: ~0.74
F1: ~0.39
ROC-AUC: ~0.67
PR-AUC: ~0.30

Because the current dataset is synthetic and failure labels are limited, Model 3 should be interpreted as a prototype risk signal rather than a field-validated safety predictor.

Optimization Workflow
Read the latest well state.
Generate CSS + SRP candidate scenarios.
Calculate dependent steam, mechanical, and energy values.
Run the trained models on candidate scenarios.
Filter scenarios using operating constraints.
Score feasible scenarios using production, risk, energy, and steam-related objectives.
Save the selected recommendation for engineer review.

The current prototype evaluates up to 1,000 candidate scenarios per request.

Human-in-the-Loop

WellWise is intentionally designed as a decision-support system, not an autonomous control system.

AI Recommendation
       ↓
Engineer Review
       ↓
Approve / Modify + Re-simulate / Reject
       ↓
Persistent Decision Record

The final operational decision remains with the engineer.

Prototype Data Scope

The current demonstration uses simulated Baghewala telemetry for 30 wells with six-hour sampling.

The prototype should not be interpreted as direct evidence of production performance in the real Baghewala field. Real-world deployment would require validated field data, instrumentation integration, operating procedures, additional failure labels, and domain validation.

Project Structure
wellwise-sih/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── optimizer.py
│   │   ├── simulator.py
│   │   └── supabase_client.py
│   ├── models/
│   ├── data/
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── services/
│       ├── App.tsx
│       ├── App.css
│       └── WellWiseTheme.css
│
└── README.md
Local Setup
Requirements
Python 3.13.x
Node.js
npm
Supabase project
Clone Repository
git clone https://github.com/Bhuvanesh0097/wellwise-sih.git
cd wellwise-sih
Backend
cd backend
python -m venv .venv

Windows:

.venv\Scripts\activate

Linux/macOS:

source .venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Create backend/.env:

SUPABASE_URL=your_supabase_project_url
SUPABASE_SECRET_KEY=your_supabase_secret_key

Never commit .env or expose the secret key.

Run the API:

uvicorn app.main:app --reload
Frontend

Open another terminal:

cd frontend
npm install
npm run dev

Production build:

npm run build
Live Prototype

WellWise Live Demo

https://wellwise-sih-2.onrender.com/

Repository

https://github.com/Bhuvanesh0097/wellwise-sih

Smart India Hackathon 2026

Team: WellWise

Problem Statement:

Digital Twin for Well-to-Surface Optimization of Cyclic Steam Stimulation (CSS) and Sucker Rod Pump (SRP) Operations for Heavy Oil Wells of Baghewala Field.

Project Highlights

AI Prediction
→ 24-hour reservoir, production and equipment-risk predictions

Digital Twin
→ Unified well-to-surface system representation

What-If Simulation
→ Test CSS + SRP scenarios virtually

Optimization
→ Evaluate feasible operating combinations

Engineer Review
→ Approve, modify or reject recommendations

License

For project, prototype, and hackathon demonstration purposes.
