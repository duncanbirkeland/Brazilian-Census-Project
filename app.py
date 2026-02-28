# app.py
from functools import wraps
import geopandas as gpd
import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify
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

def build_dropdown_data(payload: dict) -> dict:
    """
    Returns a structure for the frontend to:
      - multi-select categories
      - find intersection of tables across selected categories
      - rank tables by fewest extra categories beyond the selection
      - then drill down into variables/demographics/options
    """

    categories_map = payload.get("categories", {}) or {}
    tables = payload.get("tables", {}) or {}

    out_tables = {}

    for tid, t in tables.items():
        demographics = t.get("demographics", []) or []
        class_members = t.get("classification_members", {}) or []

        # ✅ variables: convert to value/label for dropdown
        variables = [
            {
                "value": str(v.get("variable_id")) if isinstance(v, dict) else str(v),
                "label": v.get("variable_name") if isinstance(v, dict) else str(v),
            }
            for v in (t.get("variables", []) or [])
        ]

        out_tables[str(tid)] = {
            "table_name": t.get("table_name"),
            "categories": t.get("categories", []) or [],
            "variables": variables,
            "demographics": demographics,

            # ✅ NEW: pass classification (dimension) IDs to frontend
            # demographic name -> classification id (used in /c{ID}/...)
            "classification_ids": t.get("classification_ids", {}) or {},

            # ✅ UPDATED: convert id/name to value/label for dropdown
            "classification_members": {
                d: [
                    {
                        "value": str(m.get("id")) if isinstance(m, dict) else str(m),
                        "label": m.get("name") if isinstance(m, dict) else str(m),
                    }
                    for m in (class_members.get(d, []) or [])
                ]
                for d in demographics
            },
        }

    # ensure table ids are strings (frontend-friendly)
    out_categories = {
        k: [str(x) for x in (v or [])]
        for k, v in categories_map.items()
    }

    return {
        "categories": out_categories,
        "tables": out_tables,
    }

# Load once at startup
CATALOG = load_catalog()
DROPDOWN_DATA = build_dropdown_data(CATALOG)

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper

# ---------- Routes ----------

from pathlib import Path
import json
import folium
import geopandas as gpd

@app.route("/")
def home():
    # --- Load shapefile (all parts must be in same folder) ---
    shp_path = Path(app.static_folder) / "br_regioes_2022" / "BR_Regioes_2022.shp"
    if not shp_path.exists():
        raise FileNotFoundError(f"Missing shapefile: {shp_path}")

    gdf = gpd.read_file(shp_path)

    # Reproject to WGS84 (Leaflet expects lat/lon)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Convert to GeoJSON dict (includes attributes -> properties)
    brazil_geojson = json.loads(gdf.to_json())

    # --- Map (no basemap tiles) ---
    m = folium.Map(
        location=[-14.2350, -51.9253],
        zoom_start=4,
        tiles=None
    )

    # Fit view to the layer so it shows up
    minx, miny, maxx, maxy = gdf.total_bounds
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    # Tooltip fields: take first few non-geometry columns
    cols = [c for c in gdf.columns if c != "geometry"]
    tooltip_fields = cols[:5]  # adjust or replace with specific IBGE fields

    tooltip = folium.GeoJsonTooltip(
        fields=tooltip_fields,
        aliases=[f"{c}: " for c in tooltip_fields],
        sticky=True
    ) if tooltip_fields else None

    folium.GeoJson(
        brazil_geojson,
        name="Brazil",
        style_function=lambda feature: {
            "fillColor": "#3388ff",
            "color": "#222222",
            "weight": 1,
            "fillOpacity": 0.25,
        },
        highlight_function=lambda feature: {
            "weight": 3,
            "fillOpacity": 0.45,
        },
        tooltip=tooltip
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

@app.route("/api/sidra-data", methods=["POST"])
def sidra_data():
    data = request.json

    table = data.get("table")
    variable = data.get("variable")
    classification = data.get("classification_code")
    category = data.get("category")

    if not all([table, variable]):
        return jsonify({"error": "Missing parameters"}), 400

    period = "2022"

    def fetch_level(level):
        url = (
            f"https://apisidra.ibge.gov.br/values/"
            f"t/{table}/v/{variable}/p/{period}/{level}/all"
        )

        if classification and category:
            url += f"/c{classification}/{category}"

        response = requests.get(url)
        raw = response.json()

        rows = raw[1:]  # remove header row

        cleaned = {}
        for row in rows:
            cleaned[str(row["D3C"])] = float(row["V"]) if row["V"] not in ["-", None] else 0

        return cleaned

    try:
        data_n2 = fetch_level("n2")  # macroregions
        data_n3 = fetch_level("n3")  # states

        return jsonify({
            "n2": data_n2,
            "n3": data_n3
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
