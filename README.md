# MedAdherence AI 🚀

An AI-powered companion platform for TB patients on long-term medication, built to reduce treatment dropout — one of the biggest challenges in India's TB, diabetes, and HIV programs.

## Problem

Patients on long-term treatment (especially TB) frequently drop off medication before completion due to missed reminders, side effects, running out of medicine, cost barriers, or lack of early intervention from health workers. This leads to drug resistance, relapse, and continued community spread — a serious public health issue in India's TB elimination goals.

## Solution

MedAdherence AI connects patients and health workers in one platform:

- **Multi-clinic support** — any number of health workers can register and manage their own patient panel, each with a unique Worker ID
- **Patient self-registration** — patients register themselves under their assigned health worker using that Worker ID
- **Daily check-ins** — patients report whether they took their dose, with structured reasons if missed (forgot, side effects, ran out of stock, cost, etc.)
- **Explainable AI-style risk scoring** — detects missed-dose patterns and classifies patients as Low / Medium / High risk, with a plain-English reason for health workers
- **Health worker dashboard** — patients sorted by risk so the most urgent cases get attention first
- **Smart reminders** — personalized SMS/WhatsApp-style messages (simulated) in English or Hindi, sent manually by health workers or automatically by a background scheduler
- **Flexible reminder scheduling** — patients set their own reminder frequency: daily, weekly, or monthly (for special pills taken less often)
- **Caregiver alerts** — high-risk patients automatically trigger a message to a family caregiver, extending the safety net beyond the patient alone
- **Two-way messaging** — patients and their assigned health worker can chat directly within the platform
- **Medicine stock tracking** — automatic pill countdown with low-stock warnings and restock flow, addressing a real but under-discussed cause of treatment dropout
- **Adherence streaks** — positive reinforcement for consistent patients, not just punitive missed-dose alerts
- **Program analytics** — health workers get an aggregate view: risk distribution, total reminders sent, low-stock patients, and the most common reasons for missed doses across their patient panel
- **Account self-service** — patients can edit their details or delete their account at any time

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite via Flask-SQLAlchemy
- **Scheduling:** APScheduler (background job checks every minute for missed reminders)
- **Frontend:** HTML, Jinja2 templates, custom CSS
- **Deployment:** Render (Gunicorn + Procfile)

## Feature Summary

| Feature | Status |
|---|---|
| Multi-worker registration & login | ✅ |
| Patient self-registration under a specific worker | ✅ |
| Daily check-in with structured missed-dose reasons | ✅ |
| One check-in per day, editable | ✅ |
| Explainable risk-scoring engine | ✅ |
| Health worker dashboard (risk-sorted) | ✅ |
| Patient detail page with full dose history | ✅ |
| Adherence streak counter | ✅ |
| Medicine stock tracking + restock | ✅ |
| Manual reminders (English/Hindi) | ✅ |
| Automatic scheduled reminders (daily/weekly/monthly) | ✅ |
| Reminder status indicator on patient dashboard | ✅ |
| Caregiver alerts for high-risk patients | ✅ |
| Two-way patient ↔ health worker messaging | ✅ |
| Program analytics dashboard | ✅ |
| Patient account edit/delete | ✅ |
| Live deployment | ✅ |

## Planned Real-World Extensions

- Voice messages and image sharing between patients and health workers (requires persistent cloud storage — not feasible on free-tier hosting)
- Real SMS/WhatsApp delivery via Twilio / WhatsApp Business API (currently simulated and logged for demo purposes)
- Integration with India's **Ni-kshay** TB program portal
- IVR/voice-based check-ins for patients without smartphones
- OTP-based phone verification instead of plain-text passwords
- Persistent production database (PostgreSQL) instead of SQLite, which resets on free-tier server restarts
- ML-based risk model trained on real adherence data (currently rule-based, chosen deliberately for explainability)

## How to Run Locally

```bash
git clone https://github.com/Naresh-v-1/medadherence-ai.git
cd medadherence-ai
python -m venv venv
venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000` in your browser.

**Demo credentials (seeded automatically on first run):**
- Health Worker ID: `TB001`
- Password: `tb2026`

## Screens

**Public**
- `/` — Landing page with both login paths

**Health Worker**
- `/worker-register` — Health worker registration
- `/login` — Health worker login
- `/dashboard` — Risk-sorted patient dashboard
- `/patients` — Patient list with stock status and messaging
- `/patient/<id>` — Individual patient detail + history
- `/worker/messages/<id>` — Chat with a specific patient
- `/reminders` — Reminders sent log
- `/analytics` — Program-level analytics

**Patient**
- `/patient-register` — Self-registration under a health worker
- `/patient-login` — Patient login
- `/patient-dashboard` — Personal dashboard (risk, streak, reminder settings)
- `/checkin/<id>` — Daily check-in (create or edit today's entry)
- `/messages` — Chat with assigned health worker
- `/my-reminders` — Personal reminders received
- `/patient-account` — Edit details or delete account

## Team / Hackathon

Built as a hackathon MVP focused on demonstrating a complete, explainable, multi-clinic adherence-support loop for TB patients in India — from patient self-service to health worker oversight to automated, personalized intervention.