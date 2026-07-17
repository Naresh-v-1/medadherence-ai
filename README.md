# MedAdherence AI 🚀

An AI-powered companion app for TB patients on long-term medication, designed to reduce treatment dropout — a major public health problem in India's TB, diabetes, and HIV programs.

## Problem

Patients on long-term treatment (especially TB) frequently drop off medication before completion due to missed reminders, side effects, running out of medicine, or lack of early intervention. This leads to drug resistance, relapse, and continued community spread.

## Solution

MedAdherence AI provides:
- **Daily check-ins** for patients to report whether they took their dose
- **AI-style risk scoring** that detects missed-dose patterns and flags patients as Low / Medium / High risk, with a clear explanation for health workers
- **Health worker dashboard** showing patients sorted by risk, so at-risk patients get attention first
- **Simulated smart reminders** (SMS/WhatsApp-style) personalized based on risk level
- **Medicine stock tracking** that warns before a patient runs out of pills
- **Patient history timeline** so health workers can see the full adherence pattern, not just a single alert

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite via Flask-SQLAlchemy
- **Frontend:** HTML, Jinja2 templates, custom CSS

## Features

| Feature | Status |
|---|---|
| Patient check-in flow | ✅ |
| Risk-scoring engine (explainable) | ✅ |
| Health worker dashboard | ✅ |
| Reminder simulation (SMS/WhatsApp-style) | ✅ |
| Medicine stock tracking & restock | ✅ |
| Patient detail + dose history | ✅ |

## Planned Real-World Extensions

- Integration with India's **Ni-kshay** TB program portal
- Real SMS/WhatsApp delivery via Twilio / WhatsApp Business API
- IVR/voice-based check-ins for patients without smartphones
- Multilingual support (Hindi + regional languages)
- Family/caregiver notification loop
- Privacy-first design for stigma-sensitive conditions (e.g., HIV)
- ML-based risk model trained on real adherence data (currently rule-based for explainability and speed)

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

## Screens

- `/` — Landing page
- `/patients` — Patient check-in list
- `/checkin/<id>` — Daily check-in form
- `/dashboard` — Health worker risk dashboard
- `/patient/<id>` — Individual patient detail + history
- `/reminders` — Simulated reminders log

## Team / Hackathon

Built as a 1-day hackathon MVP focused on demonstrating a real, explainable adherence-risk detection loop for TB patients in India.