import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medadherence.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "hackathon-demo-secret-key"  # simple secret for session, fine for demo

HEALTH_WORKER_PASSWORD = "tb2026"  # simple hardcoded password for demo purposes

db = SQLAlchemy(app)


# ---------- DATABASE MODELS ----------

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer)
    treatment_start_date = db.Column(db.DateTime, default=datetime.utcnow)
    dose_time = db.Column(db.String(10), default="20:00")
    pills_remaining = db.Column(db.Integer, default=10)
    caregiver_name = db.Column(db.String(100))
    caregiver_phone = db.Column(db.String(20))

    dose_logs = db.relationship('DoseLog', backref='patient', lazy=True)

    def __repr__(self):
        return f"<Patient {self.name}>"


class DoseLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)  # "taken", "missed", "side_effects"
    barrier = db.Column(db.String(30))  # forgot, side_effects, out_of_stock, cost, feeling_better, other
    note = db.Column(db.String(200))

    def __repr__(self):
        return f"<DoseLog {self.patient_id} - {self.status}>"


class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    channel = db.Column(db.String(20), default="SMS")  # SMS / WhatsApp (simulated)

    patient = db.relationship('Patient')

    def __repr__(self):
        return f"<Reminder to {self.patient_id}>"


# ---------- RISK ENGINE ----------

def calculate_risk(patient):
    """
    Looks at a patient's last 7 dose logs and returns:
    - risk level: 'Low', 'Medium', 'High'
    - reason: explanation string for the health worker
    """
    logs = DoseLog.query.filter_by(patient_id=patient.id).order_by(DoseLog.date.desc()).limit(7).all()

    if len(logs) == 0:
        return "Medium", "No check-ins yet since starting treatment."

    total_logs = len(logs)
    missed_count = sum(1 for log in logs if log.status == "missed")

    # How many days since last check-in of any kind
    last_log_date = logs[0].date
    days_since_last_checkin = (datetime.utcnow() - last_log_date).days

    # Check most recent 3 logs for consecutive misses
    recent_3 = logs[:3]
    consecutive_missed = all(log.status == "missed" for log in recent_3) if len(recent_3) == 3 else False

    # ---- Decision rules ----
    if consecutive_missed:
        return "High", f"Missed last {len(recent_3)} consecutive doses — urgent follow-up needed."

    if days_since_last_checkin >= 3:
        return "High", f"No check-in for {days_since_last_checkin} days."

    if missed_count >= 3:
        return "High", f"Missed {missed_count} of last {total_logs} doses."

    if missed_count >= 1:
        return "Medium", f"Missed {missed_count} of last {total_logs} doses — worth monitoring."

    return "Low", "Consistently taking doses on schedule."

def calculate_streak(patient):
    """Counts consecutive most-recent days where the dose was taken (not missed)."""
    logs = DoseLog.query.filter_by(patient_id=patient.id).order_by(DoseLog.date.desc()).all()

    streak = 0
    for log in logs:
        if log.status in ("taken", "side_effects"):
            streak += 1
        else:
            break
    return streak

def generate_reminder_message(patient, risk_level, reason, language="en"):
    """Builds a reminder message tailored to risk level, in English or Hindi."""

    messages = {
        "en": {
            "High": f"Hi {patient.name}, we noticed you may have missed recent TB doses. "
                    f"Your health worker has been notified and may visit soon. "
                    f"Please take your dose today — it matters for your recovery.",
            "Medium": f"Hi {patient.name}, this is a reminder to take your TB medicine at "
                      f"{patient.dose_time}. Missing doses can slow your recovery — you're doing well, keep going!",
            "Low": f"Hi {patient.name}, reminder: please take your TB dose at {patient.dose_time} today. "
                   f"Great job staying consistent!"
        },
        "hi": {
            "High": f"नमस्ते {patient.name}, लगता है आपने हाल ही में टीबी की दवा नहीं ली है। "
                    f"आपके स्वास्थ्य कार्यकर्ता को सूचित कर दिया गया है और वे जल्द ही आपसे मिल सकते हैं। "
                    f"कृपया आज अपनी दवा जरूर लें — यह आपके ठीक होने के लिए जरूरी है।",
            "Medium": f"नमस्ते {patient.name}, यह एक याद दिलाने वाला संदेश है — कृपया अपनी टीबी की दवा "
                      f"{patient.dose_time} बजे लें। दवा छोड़ने से रिकवरी धीमी हो सकती है — आप अच्छा कर रहे हैं, ऐसे ही जारी रखें!",
            "Low": f"नमस्ते {patient.name}, याद दिलाना चाहते हैं — कृपया आज {patient.dose_time} बजे अपनी टीबी की दवा लें। "
                   f"नियमित रहने के लिए बहुत बढ़िया!"
        }
    }

    return messages.get(language, messages["en"]).get(risk_level, messages["en"]["Low"])

# ---------- ROUTES ----------

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/patients")
def patients():
    all_patients = Patient.query.all()
    return render_template("patients.html", patients=all_patients)


@app.route("/restock/<int:patient_id>")
def restock(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    patient.pills_remaining += 10  # simulate a fresh 10-day supply given
    db.session.commit()
    return redirect(url_for("patients"))


@app.route("/checkin/<int:patient_id>", methods=["GET", "POST"])
def checkin(patient_id):
    patient = Patient.query.get_or_404(patient_id)

    if request.method == "POST":
        status = request.form.get("status")
        barrier = request.form.get("barrier", "")
        note = request.form.get("note", "")

        new_log = DoseLog(patient_id=patient.id, status=status, barrier=barrier, note=note)
        db.session.add(new_log)

        if status in ("taken", "side_effects") and patient.pills_remaining > 0:
            patient.pills_remaining -= 1

        db.session.commit()

        return redirect(url_for("patients"))

    return render_template("checkin.html", patient=patient)

@app.route("/patient/<int:patient_id>")
def patient_detail(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    logs = DoseLog.query.filter_by(patient_id=patient.id).order_by(DoseLog.date.desc()).all()
    risk_level, reason = calculate_risk(patient)
    streak = calculate_streak(patient)

    return render_template("patient_detail.html", patient=patient, logs=logs, risk=risk_level, reason=reason, streak=streak)

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    all_patients = Patient.query.all()
    patient_data = []

    for p in all_patients:
        risk_level, reason = calculate_risk(p)
        patient_data.append({
            "id": p.id,
            "name": p.name,
            "phone": p.phone,
            "risk": risk_level,
            "reason": reason
        })

    # Sort so High risk patients show at the top
    risk_order = {"High": 0, "Medium": 1, "Low": 2}
    patient_data.sort(key=lambda x: risk_order[x["risk"]])

    return render_template("dashboard.html", patients=patient_data)


@app.route("/send-reminders")
def send_reminders():
    language = request.args.get("lang", "en")
    all_patients = Patient.query.all()
    count = 0

    for p in all_patients:
        risk_level, reason = calculate_risk(p)
        message = generate_reminder_message(p, risk_level, reason, language=language)

        reminder = Reminder(patient_id=p.id, message=message, channel="SMS")
        db.session.add(reminder)
        count += 1

        # For High risk patients, also simulate notifying the caregiver
        if risk_level == "High" and p.caregiver_name:
            caregiver_message = (
                f"Hello {p.caregiver_name}, this is a health alert regarding {p.name}'s TB treatment. "
                f"They may have missed recent doses. Please check in with them and encourage them to continue treatment."
            )
            caregiver_reminder = Reminder(
                patient_id=p.id,
                message=f"[To Caregiver: {p.caregiver_name}] {caregiver_message}",
                channel="SMS (Caregiver)"
            )
            db.session.add(caregiver_reminder)
            count += 1

    db.session.commit()
    return redirect(url_for("reminders_log"))


@app.route("/reminders")
def reminders_log():
    all_reminders = Reminder.query.order_by(Reminder.sent_at.desc()).all()
    return render_template("reminders.html", reminders=all_reminders)


# ---------- SEED SAMPLE DATA ----------

def seed_data():
    if Patient.query.count() == 0:
        p1 = Patient(name="Ramesh Kumar", phone="9876543210", age=45, dose_time="20:00", pills_remaining=2,caregiver_name="Sunil Kumar (Son)", caregiver_phone="9876543211")
        p2 = Patient(name="Sunita Devi", phone="9876500000", age=38, dose_time="09:00", pills_remaining=8,caregiver_name="Meena Devi (Sister)", caregiver_phone="9876500001")
        p3 = Patient(name="Ali Sheikh", phone="9876511111", age=52, dose_time="21:00", pills_remaining=1,caregiver_name="Fatima Sheikh (Wife)", caregiver_phone="9876511112")
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        # Add some sample dose logs to make the risk engine show different results
        now = datetime.utcnow()

        # Ramesh: missed last 3 in a row -> should show High risk
        for i in range(5):
            status = "missed" if i < 3 else "taken"
            log = DoseLog(patient_id=p1.id, status=status, date=now - timedelta(days=i))
            db.session.add(log)

        # Sunita: all taken -> should show Low risk
        for i in range(5):
            log = DoseLog(patient_id=p2.id, status="taken", date=now - timedelta(days=i))
            db.session.add(log)

        # Ali: 1 missed -> should show Medium risk
        for i in range(5):
            status = "missed" if i == 1 else "taken"
            log = DoseLog(patient_id=p3.id, status=status, date=now - timedelta(days=i))
            db.session.add(log)

        db.session.commit()
        print("Sample patients and dose logs added!")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        if password == HEALTH_WORKER_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "Incorrect password. Try again."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)