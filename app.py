from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medadherence.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ---------- DATABASE MODELS ----------

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer)
    treatment_start_date = db.Column(db.DateTime, default=datetime.utcnow)
    dose_time = db.Column(db.String(10), default="20:00")

    dose_logs = db.relationship('DoseLog', backref='patient', lazy=True)

    def __repr__(self):
        return f"<Patient {self.name}>"


class DoseLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)  # "taken", "missed", "side_effects"
    note = db.Column(db.String(200))

    def __repr__(self):
        return f"<DoseLog {self.patient_id} - {self.status}>"


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


# ---------- ROUTES ----------

@app.route("/")
def home():
    return "<h1>MedAdherence AI is running 🚀</h1><p><a href='/dashboard'>Health Worker Dashboard</a> | <a href='/patients'>Patient Check-in List</a></p>"


@app.route("/patients")
def patients():
    all_patients = Patient.query.all()
    return render_template("patients.html", patients=all_patients)


@app.route("/checkin/<int:patient_id>", methods=["GET", "POST"])
def checkin(patient_id):
    patient = Patient.query.get_or_404(patient_id)

    if request.method == "POST":
        status = request.form.get("status")
        note = request.form.get("note", "")

        new_log = DoseLog(patient_id=patient.id, status=status, note=note)
        db.session.add(new_log)
        db.session.commit()

        return redirect(url_for("patients"))

    return render_template("checkin.html", patient=patient)


@app.route("/dashboard")
def dashboard():
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


# ---------- SEED SAMPLE DATA ----------

def seed_data():
    if Patient.query.count() == 0:
        p1 = Patient(name="Ramesh Kumar", phone="9876543210", age=45, dose_time="20:00")
        p2 = Patient(name="Sunita Devi", phone="9876500000", age=38, dose_time="09:00")
        p3 = Patient(name="Ali Sheikh", phone="9876511111", age=52, dose_time="21:00")
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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)