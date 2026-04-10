import os
import datetime
import random
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

# ── App & Config ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "energyguard-secret-key-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(BASE_DIR, "instance", "energyguard.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

# ── Models ────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80),  unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ── Dummy Energy Data ─────────────────────────────────────────────────────────
def get_energy_data(user_id):
    today = datetime.date.today()
    seed_val = user_id + today.toordinal()
    rng = random.Random(seed_val)
    
    labels = [(today - datetime.timedelta(days=6 - i)).strftime("%a") for i in range(7)]
    
    base_usage = rng.uniform(80.0, 200.0)
    solar_ratio = rng.uniform(0.1, 0.4)
    
    chart_usage = [round(rng.uniform(base_usage*0.8, base_usage*1.2)) for _ in range(7)]
    chart_solar = [round(u * rng.uniform(solar_ratio*0.8, solar_ratio*1.2)) for u in chart_usage]
    
    today_u = chart_usage[-1] + rng.uniform(-5.0, 5.0)
    today_s = chart_solar[-1] + rng.uniform(-2.0, 2.0)
    
    devices = [
        {"icon": "💡", "name": "HVAC System",      "usage": round(today_u * 0.35, 1), "status": rng.choice(["active", "idle", "active"])},
        {"icon": "🖥️", "name": "Data Centre",      "usage": round(today_u * 0.25, 1), "status": rng.choice(["active", "active", "idle"])},
        {"icon": "🔌", "name": "EV Chargers",       "usage": round(today_u * 0.15, 1), "status": rng.choice(["active", "idle"])},
        {"icon": "⚡", "name": "Production Line",   "usage": round(today_u * 0.15, 1), "status": "active"},
        {"icon": "💧", "name": "Water Pumps",       "usage": round(today_u * 0.05, 1), "status": "idle"},
        {"icon": "🌡️", "name": "Cooling Tower",    "usage": round(today_u * 0.05, 1), "status": "idle"},
    ]
    
    all_alerts = [
        {"type": "warning", "msg": f"HVAC Unit consumption {rng.randint(10, 30)}% above baseline"},
        {"type": "success", "msg": "Solar array operating at peak efficiency"},
        {"type": "info",    "msg": f"Scheduled maintenance: Grid Section {rng.choice(['A', 'B', 'C'])}"},
        {"type": "warning", "msg": f"Battery backup at {rng.randint(20, 60)}% — consider recharging"},
        {"type": "success", "msg": "Grid export credits accrued"},
        {"type": "info",    "msg": "Firmware update available for Smart Meter"}
    ]
    
    return {
        "today_usage": f"{round(today_u, 1)} kWh",
        "solar_today": f"{round(today_s, 1)} kWh",
        "grid_load":   rng.randint(40, 95),
        "co2_saved":   f"{round(today_s * 0.5, 1)} kg",
        "cost_today":  f"{round((today_u - today_s) * 0.18, 2)}",
        "chart_labels": labels,
        "chart_usage":  chart_usage,
        "chart_solar":  chart_solar,
        "devices": devices,
        "alerts": rng.sample(all_alerts, k=rng.choice([3, 4])),
    }

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username         = request.form.get("username", "").strip()
        email            = request.form.get("email", "").strip().lower()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
        else:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            flash("Account created! Please sign in.", "success")
            return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        remember   = bool(request.form.get("remember"))

        user = (
            User.query.filter_by(username=identifier).first()
            or User.query.filter_by(email=identifier.lower()).first()
        )
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            user.last_login = datetime.datetime.utcnow()
            db.session.commit()
            flash(f"Welcome back, {user.username}! 👋", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    all_users = User.query.all() if current_user.username == 'admin' else None
    return render_template("dashboard.html", energy=get_energy_data(current_user.id), all_users=all_users)

@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.username != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))
    
    user_to_delete = db.session.get(User, user_id)
    if not user_to_delete:
        flash("User not found.", "danger")
    elif user_to_delete.username == 'admin':
        flash("Cannot delete the admin user.", "danger")
    else:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f"User {user_to_delete.username} has been removed.", "success")
    
    return redirect(url_for("dashboard"))

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Access forbidden."), 403

# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
