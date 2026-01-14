# app.py
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)
import folium
import json
from pathlib import Path

from model import db, User

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-to-a-long-random-string"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# ---------- Catalog loading + dropdown data ----------

# Make the JSON path robust relative to this file (not the working directory)
CATALOG_PATH = Path(__file__).resolve().parent / "sidra_catalog_2022_api_multi_category_prefix.json"

def load_catalog() -> dict:
    with CATALOG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def select_one_table_per_category(payload: dict) -> dict:
    """
    Returns mapping: category -> table_id
    Picks the first table_id in each category list that exists in payload["tables"].
    """
    categories = payload.get("categories", {})
    tables = payload.get("tables", {})
    chosen = {}

    for category, table_ids in categories.items():
        if not table_ids:
            continue
        for tid in table_ids:
            tid = str(tid)
            if tid in tables:
                chosen[category] = tid
                break

    return chosen

def build_dropdown_data(payload: dict) -> dict:
    """
    Structure sent to the template:

    {
      "population": {
        "table_name": "...",
        "variables": {
          "População residente": {
            "demographics": {
              "Sexo": ["Total","Homens",...],
              "Lugar de nascimento": [...]
            }
          },
          ...
        }
      },
      ...
    }
    """
    tables = payload.get("tables", {})
    chosen = select_one_table_per_category(payload)

    out = {}
    for category, table_id in chosen.items():
        t = tables.get(table_id)
        if not t:
            continue

        demographics = t.get("demographics", []) or []
        class_members = t.get("classification_members", {}) or {}

        demo_map = {d: class_members.get(d, []) for d in demographics}

        var_map = {}
        for v in (t.get("variables", []) or []):
            var_name = v.get("variable_name")
            if not var_name:
                continue
            # Your requirement: demographics available for that variable.
            # In your catalog sample, variables share the same demographics per table,
            # so we attach the table demographics to each variable.
            var_map[var_name] = {"demographics": demo_map}

        out[category] = {
            "table_name": t.get("table_name"),
            "variables": var_map
        }

    return out

# Load once at startup
CATALOG = load_catalog()
DROPDOWN_DATA = build_dropdown_data(CATALOG)

# ---------- Auth helper ----------

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper

# ---------- Routes ----------

@app.route("/")
def home():
    # Center of Brazil
    m = folium.Map(
        location=[-14.2350, -51.9253],
        zoom_start=4,
        tiles="cartodbpositron"
    )

    folium.Marker(
        location=[-15.793889, -47.882778],
        popup="Brazil"
    ).add_to(m)

    map_html = m._repr_html_()

    return render_template(
        "index.html",
        title="Brazilian census data",
        map_html=map_html,
        dropdown_data=DROPDOWN_DATA
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("login"))

        user = User(email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html", title="Register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        session["user_email"] = user.email
        return redirect(url_for("home"))

    return render_template("login.html", title="Login")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
