from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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


# ---------- ROUTES ----------

@app.route("/")
def home():
    return "<h1>MedAdherence AI is running 🚀</h1><p><a href='/patients'>View Patients</a></p>"


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


# ---------- SEED SAMPLE DATA ----------

def seed_data():
    if Patient.query.count() == 0:
        p1 = Patient(name="Ramesh Kumar", phone="9876543210", age=45, dose_time="20:00")
        p2 = Patient(name="Sunita Devi", phone="9876500000", age=38, dose_time="09:00")
        p3 = Patient(name="Ali Sheikh", phone="9876511111", age=52, dose_time="21:00")
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        print("Sample patients added!")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)