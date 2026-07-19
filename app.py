import os
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medadherence.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "hackathon-demo-secret-key"

db = SQLAlchemy(app)


# ---------- DATABASE MODELS ----------

class HealthWorker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    worker_code = db.Column(db.String(20), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    password = db.Column(db.String(100), nullable=False)

    patients = db.relationship('Patient', backref='health_worker', lazy=True)

    def __repr__(self):
        return f"<HealthWorker {self.name} ({self.worker_code})>"


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(100))
    age = db.Column(db.Integer)
    treatment_start_date = db.Column(db.DateTime, default=datetime.now)
    dose_time = db.Column(db.String(10), default="20:00")
    pills_remaining = db.Column(db.Integer, default=10)
    caregiver_name = db.Column(db.String(100))
    caregiver_phone = db.Column(db.String(20))

    reminder_frequency = db.Column(db.String(10), default="daily")
    reminder_day_of_week = db.Column(db.Integer)
    reminder_day_of_month = db.Column(db.Integer)
    last_auto_reminder_date = db.Column(db.String(10))

    health_worker_id = db.Column(db.Integer, db.ForeignKey('health_worker.id'))

    dose_logs = db.relationship('DoseLog', backref='patient', lazy=True)

    def __repr__(self):
        return f"<Patient {self.name}>"


class DoseLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), nullable=False)
    barrier = db.Column(db.String(30))
    note = db.Column(db.String(200))

    def __repr__(self):
        return f"<DoseLog {self.patient_id} - {self.status}>"


class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.now)
    channel = db.Column(db.String(20), default="SMS")

    patient = db.relationship('Patient')

    def __repr__(self):
        return f"<Reminder to {self.patient_id}>"


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    health_worker_id = db.Column(db.Integer, db.ForeignKey('health_worker.id'), nullable=False)
    sender = db.Column(db.String(10), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Message from {self.sender}>"


# ---------- RISK ENGINE ----------

def calculate_risk(patient):
    logs = DoseLog.query.filter_by(patient_id=patient.id).order_by(DoseLog.date.desc()).limit(7).all()

    if len(logs) == 0:
        return "Medium", "No check-ins yet since starting treatment."

    total_logs = len(logs)
    missed_count = sum(1 for log in logs if log.status == "missed")

    last_log_date = logs[0].date
    days_since_last_checkin = (datetime.now() - last_log_date).days

    recent_3 = logs[:3]
    consecutive_missed = all(log.status == "missed" for log in recent_3) if len(recent_3) == 3 else False

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
    logs = DoseLog.query.filter_by(patient_id=patient.id).order_by(DoseLog.date.desc()).all()

    streak = 0
    for log in logs:
        if log.status in ("taken", "side_effects"):
            streak += 1
        else:
            break
    return streak


def generate_reminder_message(patient, risk_level, reason, language="en"):
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


def send_auto_reminder_if_needed():
    with app.app_context():
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        current_time_str = now.strftime("%H:%M")

        all_patients = Patient.query.all()

        for patient in all_patients:
            if patient.last_auto_reminder_date == today_str:
                continue

            should_remind_today = False

            if patient.reminder_frequency == "daily":
                should_remind_today = True
            elif patient.reminder_frequency == "weekly":
                if patient.reminder_day_of_week is not None and now.weekday() == patient.reminder_day_of_week:
                    should_remind_today = True
            elif patient.reminder_frequency == "monthly":
                if patient.reminder_day_of_month and now.day == patient.reminder_day_of_month:
                    should_remind_today = True

            if not should_remind_today:
                continue

            if current_time_str < (patient.dose_time or "20:00"):
                continue

            todays_log = DoseLog.query.filter_by(patient_id=patient.id).filter(
                DoseLog.date >= datetime(now.year, now.month, now.day)
            ).first()

            if todays_log:
                continue

            risk_level, reason = calculate_risk(patient)
            message = generate_reminder_message(patient, risk_level, reason, language="en")

            reminder = Reminder(
                patient_id=patient.id,
                message=f"[AUTO] {message}",
                channel="SMS (Auto)"
            )
            db.session.add(reminder)

            patient.last_auto_reminder_date = today_str
            db.session.commit()

            print(f"Auto-reminder sent to {patient.name}")


# ---------- ROUTES ----------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/patients")
def patients():
    worker_id = session.get("worker_id")
    if not worker_id:
        return redirect(url_for("login"))

    all_patients = Patient.query.filter_by(health_worker_id=worker_id).all()
    return render_template("patients.html", patients=all_patients)


@app.route("/restock/<int:patient_id>")
def restock(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    patient.pills_remaining += 10
    db.session.commit()
    return redirect(url_for("patients"))


@app.route("/checkin/<int:patient_id>", methods=["GET", "POST"])
def checkin(patient_id):
    logged_in_patient_id = session.get("patient_id")

    if not logged_in_patient_id:
        return redirect(url_for("patient_login"))

    if logged_in_patient_id != patient_id:
        return redirect(url_for("patient_dashboard"))

    patient = Patient.query.get_or_404(patient_id)

    now = datetime.now()
    start_of_today = datetime(now.year, now.month, now.day)
    todays_log = DoseLog.query.filter_by(patient_id=patient.id).filter(
        DoseLog.date >= start_of_today
    ).first()

    if request.method == "POST":
        status = request.form.get("status")
        barrier = request.form.get("barrier", "")
        note = request.form.get("note", "")

        if todays_log:
            old_status = todays_log.status
            was_counted = old_status in ("taken", "side_effects")
            will_count = status in ("taken", "side_effects")

            if was_counted and not will_count:
                patient.pills_remaining += 1
            elif not was_counted and will_count and patient.pills_remaining > 0:
                patient.pills_remaining -= 1

            todays_log.status = status
            todays_log.barrier = barrier
            todays_log.note = note
        else:
            new_log = DoseLog(patient_id=patient.id, status=status, barrier=barrier, note=note)
            db.session.add(new_log)

            if status in ("taken", "side_effects") and patient.pills_remaining > 0:
                patient.pills_remaining -= 1

        db.session.commit()

        return redirect(url_for("patient_dashboard"))

    return render_template("checkin.html", patient=patient, todays_log=todays_log)


@app.route("/patient/<int:patient_id>")
def patient_detail(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    logs = DoseLog.query.filter_by(patient_id=patient.id).order_by(DoseLog.date.desc()).all()
    risk_level, reason = calculate_risk(patient)
    streak = calculate_streak(patient)

    return render_template("patient_detail.html", patient=patient, logs=logs, risk=risk_level, reason=reason, streak=streak)


@app.route("/dashboard")
def dashboard():
    worker_id = session.get("worker_id")
    if not worker_id:
        return redirect(url_for("login"))

    all_patients = Patient.query.filter_by(health_worker_id=worker_id).all()
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

    risk_order = {"High": 0, "Medium": 1, "Low": 2}
    patient_data.sort(key=lambda x: risk_order[x["risk"]])

    return render_template("dashboard.html", patients=patient_data)


@app.route("/analytics")
def analytics():
    worker_id = session.get("worker_id")
    if not worker_id:
        return redirect(url_for("login"))

    all_patients = Patient.query.filter_by(health_worker_id=worker_id).all()
    total_patients = len(all_patients)

    risk_counts = {"High": 0, "Medium": 0, "Low": 0}
    for p in all_patients:
        risk_level, _ = calculate_risk(p)
        risk_counts[risk_level] += 1

    patient_ids = [p.id for p in all_patients]
    total_reminders_sent = Reminder.query.filter(Reminder.patient_id.in_(patient_ids)).count() if patient_ids else 0

    barrier_counts = {}
    missed_logs = DoseLog.query.filter(DoseLog.status == "missed", DoseLog.patient_id.in_(patient_ids)).all() if patient_ids else []
    for log in missed_logs:
        reason = log.barrier or "not_specified"
        barrier_counts[reason] = barrier_counts.get(reason, 0) + 1

    sorted_barriers = sorted(barrier_counts.items(), key=lambda x: x[1], reverse=True)

    low_stock_count = sum(1 for p in all_patients if p.pills_remaining <= 3)

    return render_template(
        "analytics.html",
        total_patients=total_patients,
        risk_counts=risk_counts,
        total_reminders_sent=total_reminders_sent,
        sorted_barriers=sorted_barriers,
        low_stock_count=low_stock_count
    )


@app.route("/send-reminders")
def send_reminders():
    worker_id = session.get("worker_id")
    if not worker_id:
        return redirect(url_for("login"))

    language = request.args.get("lang", "en")
    all_patients = Patient.query.filter_by(health_worker_id=worker_id).all()
    count = 0

    for p in all_patients:
        risk_level, reason = calculate_risk(p)
        message = generate_reminder_message(p, risk_level, reason, language=language)

        reminder = Reminder(patient_id=p.id, message=message, channel="SMS")
        db.session.add(reminder)
        count += 1

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
    worker_id = session.get("worker_id")
    if not worker_id:
        return redirect(url_for("login"))

    all_reminders = Reminder.query.join(Patient).filter(
        Patient.health_worker_id == worker_id
    ).order_by(Reminder.sent_at.desc()).all()
    return render_template("reminders.html", reminders=all_reminders)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        worker_code = request.form.get("worker_code")
        password = request.form.get("password")
        worker = HealthWorker.query.filter_by(worker_code=worker_code).first()

        if worker and worker.password == password:
            session["worker_id"] = worker.id
            return redirect(url_for("dashboard"))
        else:
            error = "Incorrect Worker ID or password."

    return render_template("login.html", error=error)


@app.route("/worker-register", methods=["GET", "POST"])
def worker_register():
    error = None
    if request.method == "POST":
        name = request.form.get("name")
        worker_code = request.form.get("worker_code")
        phone = request.form.get("phone")
        password = request.form.get("password")

        existing = HealthWorker.query.filter_by(worker_code=worker_code).first()
        if existing:
            error = "That Worker ID is already taken. Please choose another."
        else:
            new_worker = HealthWorker(name=name, worker_code=worker_code, phone=phone, password=password)
            db.session.add(new_worker)
            db.session.commit()
            session["worker_id"] = new_worker.id
            return redirect(url_for("dashboard"))

    return render_template("worker_register.html", error=error)


@app.route("/logout")
def logout():
    session.pop("worker_id", None)
    return redirect(url_for("home"))


@app.route("/patient-register", methods=["GET", "POST"])
def patient_register():
    error = None
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        password = request.form.get("password")
        age = request.form.get("age")
        dose_time = request.form.get("dose_time") or "20:00"
        reminder_frequency = request.form.get("reminder_frequency") or "daily"
        reminder_day_of_week = request.form.get("reminder_day_of_week")
        reminder_day_of_month = request.form.get("reminder_day_of_month")
        caregiver_name = request.form.get("caregiver_name")
        caregiver_phone = request.form.get("caregiver_phone")
        worker_code = request.form.get("worker_code")

        worker = HealthWorker.query.filter_by(worker_code=worker_code).first()
        existing = Patient.query.filter_by(phone=phone).first()

        if not worker:
            error = "Invalid Health Worker ID. Please check with your health worker and try again."
        elif existing:
            error = "An account with this phone number already exists. Please log in instead."
        else:
            new_patient = Patient(
                name=name,
                phone=phone,
                password=password,
                age=int(age) if age else None,
                dose_time=dose_time,
                reminder_frequency=reminder_frequency,
                reminder_day_of_week=int(reminder_day_of_week) if reminder_day_of_week else None,
                reminder_day_of_month=int(reminder_day_of_month) if reminder_day_of_month else None,
                caregiver_name=caregiver_name,
                caregiver_phone=caregiver_phone,
                health_worker_id=worker.id
            )
            db.session.add(new_patient)
            db.session.commit()
            session["patient_id"] = new_patient.id
            return redirect(url_for("patient_dashboard"))

    return render_template("patient_register.html", error=error)


@app.route("/patient-login", methods=["GET", "POST"])
def patient_login():
    error = None
    if request.method == "POST":
        phone = request.form.get("phone")
        password = request.form.get("password")
        patient = Patient.query.filter_by(phone=phone).first()

        if patient and patient.password == password:
            session["patient_id"] = patient.id
            return redirect(url_for("patient_dashboard"))
        else:
            error = "Incorrect phone number or password."

    return render_template("patient_login.html", error=error)


@app.route("/patient-logout")
def patient_logout():
    session.pop("patient_id", None)
    return redirect(url_for("home"))


@app.route("/patient-dashboard", methods=["GET", "POST"])
def patient_dashboard():
    patient_id = session.get("patient_id")
    if not patient_id:
        return redirect(url_for("patient_login"))

    patient = Patient.query.get_or_404(patient_id)

    if request.method == "POST":
        patient.dose_time = request.form.get("dose_time") or patient.dose_time
        patient.reminder_frequency = request.form.get("reminder_frequency") or "daily"

        week_day = request.form.get("reminder_day_of_week")
        patient.reminder_day_of_week = int(week_day) if week_day else None

        month_day = request.form.get("reminder_day_of_month")
        patient.reminder_day_of_month = int(month_day) if month_day else None

        patient.caregiver_name = request.form.get("caregiver_name") or patient.caregiver_name
        patient.caregiver_phone = request.form.get("caregiver_phone") or patient.caregiver_phone

        db.session.commit()

    risk_level, reason = calculate_risk(patient)
    streak = calculate_streak(patient)
    logs = DoseLog.query.filter_by(patient_id=patient.id).order_by(DoseLog.date.desc()).limit(10).all()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")

    start_of_today = datetime(now.year, now.month, now.day)
    checked_in_today = DoseLog.query.filter_by(patient_id=patient.id).filter(
        DoseLog.date >= start_of_today
    ).first() is not None

    is_reminder_day = False
    if patient.reminder_frequency == "daily":
        is_reminder_day = True
    elif patient.reminder_frequency == "weekly":
        is_reminder_day = patient.reminder_day_of_week is not None and now.weekday() == patient.reminder_day_of_week
    elif patient.reminder_frequency == "monthly":
        is_reminder_day = patient.reminder_day_of_month is not None and now.day == patient.reminder_day_of_month

    if checked_in_today:
        reminder_status = ("done", "You've checked in today — no reminder needed.")
    elif not is_reminder_day:
        reminder_status = ("none", "No reminder scheduled for today based on your settings.")
    elif patient.last_auto_reminder_date == today_str:
        reminder_status = ("sent", "A reminder was already sent to you today.")
    elif current_time_str < (patient.dose_time or "20:00"):
        reminder_status = ("upcoming", f"Your reminder will be sent at {patient.dose_time} if you haven't checked in by then.")
    else:
        reminder_status = ("due", "Your dose time has passed — a reminder will be sent shortly if you don't check in.")

    return render_template("patient_dashboard.html", patient=patient, risk=risk_level, reason=reason, streak=streak, logs=logs, reminder_status=reminder_status)


@app.route("/my-reminders")
def my_reminders():
    patient_id = session.get("patient_id")
    if not patient_id:
        return redirect(url_for("patient_login"))

    patient = Patient.query.get_or_404(patient_id)

    my_reminders_list = Reminder.query.filter_by(patient_id=patient.id).filter(
        Reminder.channel.in_(["SMS", "SMS (Auto)"])
    ).order_by(Reminder.sent_at.desc()).all()

    return render_template("my_reminders.html", patient=patient, reminders=my_reminders_list)


@app.route("/patient-account", methods=["GET", "POST"])
def patient_account():
    patient_id = session.get("patient_id")
    if not patient_id:
        return redirect(url_for("patient_login"))

    patient = Patient.query.get_or_404(patient_id)
    error = None
    success = None

    if request.method == "POST":
        new_phone = request.form.get("phone")
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        existing = Patient.query.filter(Patient.phone == new_phone, Patient.id != patient.id).first()
        if existing:
            error = "That phone number is already in use by another account."
        elif new_password and new_password != confirm_password:
            error = "Passwords do not match."
        else:
            patient.name = request.form.get("name") or patient.name
            patient.phone = new_phone or patient.phone
            patient.age = int(request.form.get("age")) if request.form.get("age") else patient.age
            if new_password:
                patient.password = new_password

            db.session.commit()
            success = "Your account details have been updated."

    return render_template("patient_account.html", patient=patient, error=error, success=success)


@app.route("/patient-delete-account", methods=["POST"])
def patient_delete_account():
    patient_id = session.get("patient_id")
    if not patient_id:
        return redirect(url_for("patient_login"))

    patient = Patient.query.get_or_404(patient_id)

    DoseLog.query.filter_by(patient_id=patient.id).delete()
    Reminder.query.filter_by(patient_id=patient.id).delete()
    Message.query.filter_by(patient_id=patient.id).delete()

    db.session.delete(patient)
    db.session.commit()

    session.pop("patient_id", None)
    return redirect(url_for("home"))


@app.route("/messages", methods=["GET", "POST"])
def patient_messages():
    patient_id = session.get("patient_id")
    if not patient_id:
        return redirect(url_for("patient_login"))

    patient = Patient.query.get_or_404(patient_id)

    if not patient.health_worker_id:
        return render_template("messages.html", patient=patient, messages=[], no_worker=True)

    if request.method == "POST":
        body = request.form.get("body")
        if body and body.strip():
            new_message = Message(
                patient_id=patient.id,
                health_worker_id=patient.health_worker_id,
                sender="patient",
                body=body.strip()
            )
            db.session.add(new_message)
            db.session.commit()
        return redirect(url_for("patient_messages"))

    all_messages = Message.query.filter_by(patient_id=patient.id).order_by(Message.sent_at.asc()).all()
    return render_template("messages.html", patient=patient, messages=all_messages, no_worker=False)


@app.route("/worker/messages/<int:patient_id>", methods=["GET", "POST"])
def worker_messages(patient_id):
    worker_id = session.get("worker_id")
    if not worker_id:
        return redirect(url_for("login"))

    patient = Patient.query.get_or_404(patient_id)

    if patient.health_worker_id != worker_id:
        return redirect(url_for("patients"))

    if request.method == "POST":
        body = request.form.get("body")
        if body and body.strip():
            new_message = Message(
                patient_id=patient.id,
                health_worker_id=worker_id,
                sender="worker",
                body=body.strip()
            )
            db.session.add(new_message)
            db.session.commit()
        return redirect(url_for("worker_messages", patient_id=patient.id))

    all_messages = Message.query.filter_by(patient_id=patient.id).order_by(Message.sent_at.asc()).all()
    return render_template("worker_messages.html", patient=patient, messages=all_messages)


# ---------- SEED SAMPLE DATA ----------

def seed_data():
    if HealthWorker.query.count() == 0:
        default_worker = HealthWorker(name="Dr. Priya Sharma", worker_code="TB001", phone="9000000000", password="tb2026")
        db.session.add(default_worker)
        db.session.commit()

    if Patient.query.count() == 0:
        default_worker = HealthWorker.query.filter_by(worker_code="TB001").first()

        p1 = Patient(name="Ramesh Kumar", phone="9876543210", age=45, dose_time="20:00", pills_remaining=2,
                     caregiver_name="Sunil Kumar (Son)", caregiver_phone="9876543211", health_worker_id=default_worker.id)
        p2 = Patient(name="Sunita Devi", phone="9876500000", age=38, dose_time="09:00", pills_remaining=8,
                     caregiver_name="Meena Devi (Sister)", caregiver_phone="9876500001", health_worker_id=default_worker.id)
        p3 = Patient(name="Ali Sheikh", phone="9876511111", age=52, dose_time="21:00", pills_remaining=1,
                     caregiver_name="Fatima Sheikh (Wife)", caregiver_phone="9876511112", health_worker_id=default_worker.id)
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        now = datetime.now()

        for i in range(5):
            status = "missed" if i < 3 else "taken"
            log = DoseLog(patient_id=p1.id, status=status, date=now - timedelta(days=i))
            db.session.add(log)

        for i in range(5):
            log = DoseLog(patient_id=p2.id, status="taken", date=now - timedelta(days=i))
            db.session.add(log)

        for i in range(5):
            status = "missed" if i == 1 else "taken"
            log = DoseLog(patient_id=p3.id, status=status, date=now - timedelta(days=i))
            db.session.add(log)

        db.session.commit()
        print("Sample health worker and patients added! Worker ID: TB001 / Password: tb2026")


# ---------- APP INITIALIZATION ----------

with app.app_context():
    db.create_all()
    seed_data()

scheduler = BackgroundScheduler()
scheduler.add_job(func=send_auto_reminder_if_needed, trigger="interval", minutes=1)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)