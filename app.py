# app.py
from functools import wraps
from pathlib import Path
import json

import geopandas as gpd
import requests
import folium
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)

from model import db, User

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-to-a-long-random-string"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# ---------- Catalog loading + dropdown data ----------

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
        class_members = t.get("classification_members", {}) or {}

        # variables: convert to value/label for dropdown
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
            # ✅ NEW: demographic name -> classification id (dimension id, used in /c{ID}/...)
            "classification_ids": t.get("classification_ids", {}) or {},
            # ✅ UPDATED: id/name -> value/label for dropdown
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

    out_categories = {k: [str(x) for x in (v or [])] for k, v in categories_map.items()}

    return {"categories": out_categories, "tables": out_tables}


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

@app.route("/")
def home():
    # --- Load shapefiles ---
    regioes_path = Path(app.static_folder) / "BR_Regioes_2022" / "BR_Regioes_2022.shp"
    uf_path = Path(app.static_folder) / "BR_UF_2022" / "BR_UF_2022.shp"

    if not regioes_path.exists():
        raise FileNotFoundError(f"Missing shapefile: {regioes_path}")
    if not uf_path.exists():
        raise FileNotFoundError(f"Missing shapefile: {uf_path}")

    regioes_gdf = gpd.read_file(regioes_path)
    uf_gdf = gpd.read_file(uf_path)

    # Reproject to WGS84 (Leaflet expects lat/lon)
    if regioes_gdf.crs is not None and regioes_gdf.crs.to_epsg() != 4326:
        regioes_gdf = regioes_gdf.to_crs(epsg=4326)

    if uf_gdf.crs is not None and uf_gdf.crs.to_epsg() != 4326:
        uf_gdf = uf_gdf.to_crs(epsg=4326)

    # Optional debug: print available columns once
    print("REGIOES columns:", list(regioes_gdf.columns))
    print("UF columns:", list(uf_gdf.columns))

    # Convert to GeoJSON dict
    regioes_geojson = json.loads(regioes_gdf.to_json())
    uf_geojson = json.loads(uf_gdf.to_json())

    # --- Map ---
    m = folium.Map(
        location=[-14.2350, -51.9253],
        zoom_start=4,
        tiles=None
    )

    # Fit to Brazil bounds using regions layer
    minx, miny, maxx, maxy = regioes_gdf.total_bounds
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    # Regions layer (N2)
    regioes_layer = folium.GeoJson(
        regioes_geojson,
        name="Regions",
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
        show=True,
    )
    regioes_layer.add_to(m)

    # UF layer (N3)
    uf_layer = folium.GeoJson(
        uf_geojson,
        name="UFs",
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
        show=False,
    )
    uf_layer.add_to(m)

    map_html = m._repr_html_()

    return render_template(
        "index.html",
        title="Brazilian census data",
        map_html=map_html,
        dropdown_data=DROPDOWN_DATA,
        regioes_layer_name=regioes_layer.get_name(),
        uf_layer_name=uf_layer.get_name(),
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
    data = request.json or {}

    table = data.get("table")
    variable = data.get("variable")
    classification = data.get("classification_code")  # dimension id (for /c{ID}/...)
    category = data.get("category")                  # member id

    if not all([table, variable]):
        return jsonify({"error": "Missing parameters"}), 400

    period = "2022"

    def fetch_level(level: str):
        url = (
            f"https://apisidra.ibge.gov.br/values/"
            f"t/{table}/v/{variable}/p/{period}/{level}/all"
        )

        if classification and category:
            url += f"/c{classification}/{category}"

        response = requests.get(url, timeout=60)
        response.raise_for_status()
        raw = response.json()

        rows = raw[1:]  # remove header row

        cleaned = {}
        for row in rows:
            # D3C is the code for the geography level (n2/n3) in this endpoint response
            cleaned[str(row["D3C"])] = float(row["V"]) if row["V"] not in ["-", None] else 0

        return cleaned

    try:
        data_n2 = fetch_level("n2")  # macroregions
        data_n3 = fetch_level("n3")  # states

        return jsonify({"n2": data_n2, "n3": data_n3})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)