from functools import wraps
from pathlib import Path  # Supports path handling on multiple systems
import json  # Supports JSON parsing
from math import sqrt  # Used for Pearson correlation denominator

import requests  # HTTP client to allow for SIDRA API requests
import folium  # Used for interactive map generation
from branca.element import Element  # Used to inject custom JavaScript into the Folium map
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

from model import db, User, MapVariable, Correlation  # SQLAlchemy models and DB instance.

app = Flask(__name__)

import os

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-secret")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///app.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Assign the SQLAlchemy instance to this flask app
db.init_app(app)

# Absolute path to the English translation of the SIDRA catalog to build the dropdowns on the UI
CATALOG_PATH = Path(__file__).resolve().parent / "sidra_catalog_2022_api_multi_category_prefix_en.json"


def load_catalog() -> dict:
    """
    Load the SIDRA catalog JSON file

    Returns:
        dict: Parsed JSON content containing categories, tables, variables,
        demographics, and classification data used for the front end
    """
    with CATALOG_PATH.open("r", encoding="utf-8") as catalog_file:
        return json.load(catalog_file)


def build_dropdown_data(payload: dict) -> dict:
    """
    Transform the catalog data to be able to be used by the UI

    This function normalizes:
    - category IDs to strings
    - table IDs to strings
    - variables to {value, label}
    - classification members to {value, label}

    Arguments:
        payload (dict): Raw catalog JSON loaded from disk.

    Returns:
        dict: Simplified structure with "categories" and "tables" keys,
        designed for creating the dropdowns
    """
    categories_map = payload.get("categories", {}) or {}
    tables = payload.get("tables", {}) or {}

    normalized_tables = {}

    # Iterate through every table in the catalog and normalize its data
    for table_id, table_data in tables.items():
        demographics = table_data.get("demographics", []) or []
        class_members = table_data.get("classification_members", {}) or {}

        # Normalize variables so the frontend can use them directly in selects
        variables = [
            {
                "value": str(variable_data.get("variable_id")) if isinstance(variable_data, dict) else str(variable_data),
                "label": variable_data.get("variable_name") if isinstance(variable_data, dict) else str(variable_data),
            }
            for variable_data in (table_data.get("variables", []) or [])
        ]

        # Store a cleaned version of each table's data
        normalized_tables[str(table_id)] = {
            "table_name": table_data.get("table_name"),
            "categories": table_data.get("categories", []) or [],
            "variables": variables,
            "demographics": demographics,
            "classification_ids": table_data.get("classification_ids", {}) or {},
            "classification_members": {
                demographic: [
                    {
                        "value": str(member_data.get("id")) if isinstance(member_data, dict) else str(member_data),
                        "label": member_data.get("name") if isinstance(member_data, dict) else str(member_data),
                    }
                    for member_data in (class_members.get(demographic, []) or [])
                ]
                for demographic in demographics
            },
        }

    # Normalize category member IDs to strings
    normalized_categories = {category_id: [str(category_value) for category_value in (category_values or [])] for category_id, category_values in categories_map.items()}

    return {"categories": normalized_categories, "tables": normalized_tables}


# Precompute data once at startup to avoid repeated processing
DROPDOWN_DATA = build_dropdown_data(load_catalog())


# Cached values filled by build_base_map() so the app doesn't rebuild the map on every request
BASE_MAP_HTML = None
REGIOES_LAYER_NAME = None
UF_LAYER_NAME = None


def build_base_map():
    """
    Build and cache the application's Folium map

    This optimized version:
    - creates a lightweight Folium base map on the server
    - does not embed the large region/state GeoJSON files into the rendered HTML
    - injects JavaScript that fetches the GeoJSON files in the browser
    - stores rendered HTML and layer names in global variables
    """
    global BASE_MAP_HTML, REGIOES_LAYER_NAME, UF_LAYER_NAME

    # Use stable layer names so the frontend can continue looking them up
    # after the GeoJSON layers are created inside the iframe.
    REGIOES_LAYER_NAME = "regions_layer"
    UF_LAYER_NAME = "states_layer"

    # Create a blank base map centered on Brazil
    base_map = folium.Map(
        location=[-14.2350, -51.9253],
        zoom_start=4,
        tiles=None,
        prefer_canvas=True,
        control_scale=False,
        min_zoom=4,
        max_zoom=8,
    )

    # Fit tightly around Brazil and keep navigation focused there
    brazil_bounds = [[-34.5, -74.5], [6.5, -32.0]]

    # Slightly expanded bounds so users can pan a bit further out
    interaction_bounds = [[-45.0, -95.0], [15.0, -20.0]]

    base_map.fit_bounds(brazil_bounds, padding=(50, 50))

    # Apply softer boundary
    base_map.options["maxBounds"] = interaction_bounds
    base_map.options["maxBoundsViscosity"] = 0.6

    map_name = base_map.get_name()
    regions_url = f"{app.static_url_path}/regions.geojson"
    states_url = f"{app.static_url_path}/states.geojson"

    # Load the regions and states GeoJSON files lazily in the browser so the
    # server does not spend time rendering large inline GeoJSON into the HTML
    lazy_layer_script = f"""
    <script>
    (function () {{
      function initializeLazyGeoJsonLayers() {{
        const mapObject = window[{json.dumps(map_name)}];
        if (!mapObject || window.__lazyGeoJsonInitialized) return;
        window.__lazyGeoJsonInitialized = true;

        const regionsLayerName = {json.dumps(REGIOES_LAYER_NAME)};
        const statesLayerName = {json.dumps(UF_LAYER_NAME)};
        const regionsUrl = {json.dumps(regions_url)};
        const statesUrl = {json.dumps(states_url)};
        const brazilBounds = {json.dumps(brazil_bounds)};
        const interactionBounds = {json.dumps(interaction_bounds)};

        mapObject.fitBounds(brazilBounds, {{
          padding: [50, 50]
        }});
        mapObject.setMaxBounds(interactionBounds);

        const defaultStyle = function () {{
          return {{
            fillColor: "#d9d9d9",
            color: "#666666",
            weight: 0.8,
            fillOpacity: 0.35
          }};
        }};

        function onEachFeature(feature, layer) {{
          layer.on({{
            mouseover: function (event) {{
              const hoveredLayer = event.target;

              // Store the current style so hover keeps the current fill color
              hoveredLayer._previousStyle = {{
                fillColor: hoveredLayer.options.fillColor,
                color: hoveredLayer.options.color,
                weight: hoveredLayer.options.weight,
                fillOpacity: hoveredLayer.options.fillOpacity
              }};

              // Highlight only the border while keeping the existing fill color
              hoveredLayer.setStyle({{
                fillColor: hoveredLayer.options.fillColor,
                color: "#222222",
                weight: 2,
                fillOpacity: hoveredLayer.options.fillOpacity
              }});

              if (hoveredLayer.bringToFront) {{
                hoveredLayer.bringToFront();
              }}
            }},
            mouseout: function (event) {{
              const hoveredLayer = event.target;

              if (hoveredLayer._previousStyle) {{
                hoveredLayer.setStyle(hoveredLayer._previousStyle);
              }}
            }}
          }});
        }}

        Promise.all([
          fetch(regionsUrl).then(function (response) {{
            if (!response.ok) {{
              throw new Error("Failed to load regions GeoJSON");
            }}
            return response.json();
          }}),
          fetch(statesUrl).then(function (response) {{
            if (!response.ok) {{
              throw new Error("Failed to load states GeoJSON");
            }}
            return response.json();
          }})
        ])
          .then(function (results) {{
            const regionsGeoJson = results[0];
            const statesGeoJson = results[1];

            const regionsLayer = L.geoJSON(regionsGeoJson, {{
              style: defaultStyle,
              onEachFeature: onEachFeature
            }});

            const statesLayer = L.geoJSON(statesGeoJson, {{
              style: defaultStyle,
              onEachFeature: onEachFeature
            }});

            // Expose the layers using the same names expected by dropdowns.js
            window[regionsLayerName] = regionsLayer;
            window[statesLayerName] = statesLayer;

            // Add a regions layer that is shown by default
            regionsLayer.addTo(mapObject);

            // Add UI control to toggle between region and state layers
            const layerControl = L.control.layers(
              {{
                "Regions": regionsLayer,
                "States": statesLayer
              }},
              null,
              {{
                collapsed: false,
                position: "topright"
              }}
            ).addTo(mapObject);

            // Create a palette selector next to the layer control
            const paletteControl = L.control({{ position: "topright" }});

            paletteControl.onAdd = function () {{
              const container = L.DomUtil.create("div");

              container.style.background = "rgba(255,255,255,0.92)";
              container.style.padding = "6px 8px";
              container.style.border = "1px solid rgba(0,0,0,0.12)";
              container.style.borderRadius = "8px";
              container.style.boxShadow = "0 2px 8px rgba(0,0,0,0.12)";
              container.style.marginTop = "6px";

              container.innerHTML = `
                <label style="font-size:12px; display:block; margin-bottom:4px;">
                  Colours
                </label>
                <select id="map-palette-select" style="width:100%;">
                  <option value="Default">Default</option>
                  <option value="Green">Green</option>
                  <option value="Blue">Blue</option>
                  <option value="Red">Red</option>
                </select>
              `;

              // Prevent map dragging while interacting with the palette selector
              L.DomEvent.disableClickPropagation(container);

              return container;
            }};

            paletteControl.addTo(mapObject);

            // Forward map palette changes to the main page selector so map and legend stay in sync
            setTimeout(function () {{
              const select = document.getElementById("map-palette-select");

              if (select && window.parent && window.parent.document) {{
                const externalSelect = window.parent.document.getElementById("color-palette");

                if (externalSelect) {{
                  select.value = externalSelect.value || "brazil";
                }}

                select.addEventListener("change", function (event) {{
                  if (externalSelect) {{
                    externalSelect.value = event.target.value;
                    externalSelect.dispatchEvent(new Event("change"));
                  }}
                }});
              }}
            }}, 300);

            // Clean up the layer control appearance slightly.
            const controlContainer = layerControl.getContainer();
            if (controlContainer) {{
              controlContainer.style.background = "rgba(255, 255, 255, 0.92)";
              controlContainer.style.border = "1px solid rgba(0, 0, 0, 0.12)";
              controlContainer.style.borderRadius = "8px";
              controlContainer.style.boxShadow = "0 2px 8px rgba(0, 0, 0, 0.12)";
              controlContainer.style.padding = "4px 6px";
            }}

            // Refocus the map when switching layers so navigation feels easier.
            mapObject.on("baselayerchange", function (event) {{
              if (event.name === "Regions") {{
                mapObject.fitBounds(brazilBounds, {{
                  padding: [50, 50]
                }});
              }} else if (event.name === "States") {{
                mapObject.fitBounds(brazilBounds, {{
                  padding: [35, 35],
                  maxZoom: 5
                }});
              }}
            }});
          }})
          .catch(function (error) {{
            console.error("Failed to initialize lazy GeoJSON layers:", error);
          }});
      }}

      if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", initializeLazyGeoJsonLayers);
      }} else {{
        initializeLazyGeoJsonLayers();
      }}
    }})();
    </script>
    """

    base_map.get_root().html.add_child(Element(lazy_layer_script))

    # Cache the rendered map HTML and internal Folium layer names
    BASE_MAP_HTML = base_map._repr_html_()

def login_required(view_func):
    """
    Decorator that restricts access to authenticated users

    The @wraps(view_func) decorator keeps the wrapped function's name,
    and data which helps with Flask routing

    Arguments:
        view_func (callable): The Flask view function to protect

    Returns:
        callable: Wrapped function that redirects unauthenticated users
        to the login page
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        """
        Check whether the current session contains a logged-in user.

        If no user is logged in, flash a warning and redirect to the login page
        Otherwise, call the original view function
        """
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def fetch_sidra_series(
    table,
    variable,
    classification=None,
    category=None,
    level="n3",
    period="2022",
):
    """
    Fetch a single SIDRA series and return it as a geographic_code -> value mapping.


    Arguments:
        table (str | int): SIDRA table ID
        variable (str | int): SIDRA variable ID
        classification (str | int | None): Classification code
        category (str | int | None): Category inside the classification
        level (str): Geographic aggregation level, such as "n2" or "n3"
        period (str): Sets the period for data to the 2022 census

    Returns:
        dict: Mapping of geographic code strings to float values

    Raises:
        requests.HTTPError: If the SIDRA request fails, e.g. because the server is down
    """
    # Build the base SIDRA API URL.
    url = (
        f"https://apisidra.ibge.gov.br/values/"
        f"t/{table}/v/{variable}/p/{period}/{level}/all"
    )

    # Append classification category filter to the URL query when both are provided
    if classification and category:
        url += f"/c{classification}/{category}"

    # Call the SIDRA API and raise an exception on HTTP errors
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    response_data = response.json()

    # The first row is a header, so skip it
    data_rows = response_data[1:]
    series_by_geo_code = {}

    # Clean and convert numeric values into a dictionary keyed by D3C
    for row_data in data_rows:
        value = row_data.get("V")
        if value in ["-", None]:
            continue

        try:
            series_by_geo_code[str(row_data["D3C"])] = float(value)
        except (ValueError, TypeError, KeyError):
            # Skip invalid or incomplete rows as opposed to failing the entire request
            continue

    return series_by_geo_code


def pearson_corr(x_values, y_values):
    """
    Compute the Pearson correlation coefficient between two numeric sequences

    Arguments:
        xs (list[float]): First numeric sequence
        ys (list[float]): Second numeric sequence

    Returns:
        float | None: Pearson correlation coefficient in the range [-1, 1],
        or None if the correlation cannot be computed
    """
    # Pearson correlation requires equal-length inputs and at least 2 points.
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return None

    point_count = len(x_values)
    mean_x = sum(x_values) / point_count
    mean_y = sum(y_values) / point_count

    # Numerator: covariance component.
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))

    # Denominator components: sum of squared deviations.
    x_squared_deviation_sum = sum((x - mean_x) ** 2 for x in x_values)
    y_squared_deviation_sum = sum((y - mean_y) ** 2 for y in y_values)

    denominator = sqrt(x_squared_deviation_sum * y_squared_deviation_sum)
    if denominator == 0:
        return None

    return numerator / denominator

# ---------- Routes ----------

@app.route("/")
def home():
    global BASE_MAP_HTML

    if BASE_MAP_HTML is None:
        build_base_map()

    return render_template(
        "index.html",
        title="Brazilian census data",
        map_html=BASE_MAP_HTML,
        dropdown_data=DROPDOWN_DATA,
        regioes_layer_name=REGIOES_LAYER_NAME,
        uf_layer_name=UF_LAYER_NAME,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Register a new user.

    GET:
        Render the registration form

    POST:
        Validate email/password, reject duplicates, create the user,
        and redirect to the login page
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        # Require both email and password
        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for("register"))

        # Prevent duplicate registrations
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("login"))

        # Create the new user
        user = User(email=email)
        user.set_password(password)

        # Add the user to the database
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html", title="Register")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Authenticate an existing user

    GET:
        Render the login form

    POST:
        Check email/password, store user info in session,
        and redirect to the home page if valid
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        # Look up the user and validate the password
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        # Save login state in the session
        session["user_id"] = user.id
        session["user_email"] = user.email
        return redirect(url_for("home"))

    return render_template("login.html", title="Login")


@app.route("/logout")
def logout():
    """
    Log out the current user by clearing the session
    """
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home"))


@app.route("/api/sidra-data", methods=["POST"])
def sidra_data():
    """
    Fetch map-ready SIDRA data for both region level (n2) and state level (n3)

    Expected JSON body:
        {
            "table": "...",
            "variable": "...",
            "classification_code": "...",
            "category": "..."
        }

    Returns:
        JSON response with:
        - n2 data (regions)
        - n3 data (states)
        or an error message with appropriate HTTP status
    """
    request_data = request.json or {}

    table = request_data.get("table")
    variable = request_data.get("variable")
    classification = request_data.get("classification_code")
    category = request_data.get("category")

    # Require the minimum parameters needed to query SIDRA
    if not all([table, variable]):
        return jsonify({"error": "Missing parameters"}), 400

    try:
        # Fetch regional-level data
        region_data = fetch_sidra_series(
            table=table,
            variable=variable,
            classification=classification,
            category=category,
            level="n2",
            period="2022",
        )

        # Fetch state-level data
        state_data = fetch_sidra_series(
            table=table,
            variable=variable,
            classification=classification,
            category=category,
            level="n3",
            period="2022",
        )

        return jsonify({"n2": region_data, "n3": state_data})

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/correlate", methods=["POST"])
def correlate():
    """
    Compare two user-selected SIDRA series at the state level (n3)
    and return their Pearson correlation coefficient

    Expected JSON body:
        {
            "left": {
                "table": "...",
                "variable": "...",
                "classification_code": "...",  # optional
                "category": "..."              # optional
            },
            "right": {
                "table": "...",
                "variable": "...",
                "classification_code": "...",  # optional
                "category": "..."              # optional
            },
            "map_variable_id": ...,            # optional
            "compare_table": ...,              # optional
            "compare_variable": ...,
            "compare_demographic": ...,
            "compare_category": ...
        }

    Returns:
        JSON containing:
        - correlation score
        - number of overlapping geographic units
        - list of shared keys
    """
    request_data = request.json or {}

    left_selection = request_data.get("left") or {}
    right_selection = request_data.get("right") or {}

    # Validate the map variable is selected
    if not left_selection.get("table") or not left_selection.get("variable"):
        return jsonify({"error": "Missing primary selection"}), 400

    # Validate the comparison variable is selected
    if not right_selection.get("table") or not right_selection.get("variable"):
        return jsonify({"error": "Missing comparison selection"}), 400

    try:
        # Fetch the first series at state level.
        left_series = fetch_sidra_series(
            table=left_selection["table"],
            variable=left_selection["variable"],
            classification=left_selection.get("classification_code"),
            category=left_selection.get("category"),
            level="n3",
            period="2022",
        )

        # Fetch the second series at state level.
        right_series = fetch_sidra_series(
            table=right_selection["table"],
            variable=right_selection["variable"],
            classification=right_selection.get("classification_code"),
            category=right_selection.get("category"),
            level="n3",
            period="2022",
        )

        # Only compare states present in both datasets
        common_geo_codes = sorted(set(left_series.keys()) & set(right_series.keys()))
        if len(common_geo_codes) < 2:
            return jsonify({"error": "Not enough overlapping states to compare."}), 400

        left_values = [left_series[geo_code] for geo_code in common_geo_codes]
        right_values = [right_series[geo_code] for geo_code in common_geo_codes]

        # Compute correlation
        correlation_score = pearson_corr(left_values, right_values)

        if correlation_score is None:
            return jsonify({"error": "Correlation could not be computed."}), 400

        # Store the correlation if linked to a saved map variable
        map_variable_id = request_data.get("map_variable_id")

        if map_variable_id:
            correlation_record = Correlation(
                map_variable_id=map_variable_id,
                compared_table=request_data.get("compare_table"),
                compared_variable=request_data.get("compare_variable"),
                compared_demographic=request_data.get("compare_demographic"),
                compared_category=request_data.get("compare_category"),
                score=correlation_score,
            )
            db.session.add(correlation_record)
            db.session.commit()

        return jsonify({
            "correlation": correlation_score,
            "count": len(common_geo_codes),
            "keys": common_geo_codes,
        })

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/export-variable", methods=["POST"])
@login_required
def export_variable():
    """
    Save the currently selected map variable to the logged-in user's account

    If an identical saved variable already exists for the user, return its ID
    instead of creating a duplicate

    Returns:
        JSON response with:
        - {"status": "exists", "id": ...} if already present
        - {"status": "ok", "id": ...} if newly created
    """
    request_data = request.json or {}

    # Check whether this exact selection was already saved by the current user.
    existing_variable = MapVariable.query.filter_by(
        user_id=session["user_id"],
        table_id=request_data.get("table"),
        variable_id=request_data.get("variable"),
        demographic=request_data.get("demographic"),
        classification=request_data.get("classification"),
    ).first()

    if existing_variable:
        return jsonify({"status": "exists", "id": existing_variable.id})

    # Create and save a new map variable record
    map_variable = MapVariable(
        user_id=session["user_id"],
        table_id=request_data.get("table"),
        variable_id=request_data.get("variable"),
        demographic=request_data.get("demographic"),
        classification=request_data.get("classification"),
        label=request_data.get("label"),
    )

    db.session.add(map_variable)
    db.session.commit()

    return jsonify({"status": "ok", "id": map_variable.id})


@app.route("/api/map-variables")
@login_required
def get_map_variables():
    """
    Return all saved map variables for the logged-in user with sorted correlation results for each variable

    This route contains:
    - variable names
    - table names
    - selected classification member names
    - correlation metadata for each saved variable

    Returns:
        JSON list of saved variables and their correlations
    """
    saved_variables = MapVariable.query.filter_by(user_id=session["user_id"]).all()

    result = []

    # Build a frontend accessible representation of each saved map variable
    for saved_variable in saved_variables:
        table_meta = DROPDOWN_DATA["tables"].get(str(saved_variable.table_id), {})

        # Resolve the variable's display name using catalog metadata
        variable_name = next(
            (
                variable_option["label"]
                for variable_option in table_meta.get("variables", [])
                if str(variable_option["value"]) == str(saved_variable.variable_id)
            ),
            str(saved_variable.variable_id),
        )

        demographic_name = saved_variable.demographic or ""
        selected_option_name = ""

        # Resolve the selected classification/category name if applicable
        if saved_variable.demographic and saved_variable.classification:
            selected_option_name = next(
                (
                    classification_option["label"]
                    for classification_option in table_meta.get("classification_members", {}).get(saved_variable.demographic, [])
                    if str(classification_option["value"]) == str(saved_variable.classification)
                ),
                str(saved_variable.classification),
            )

        correlations = []

        # Convert each stored correlation into a fully labeled object
        for correlation_record in saved_variable.correlations:
            compared_table_meta = DROPDOWN_DATA["tables"].get(str(correlation_record.compared_table), {})

            # Resolve the compared variable name
            compared_variable_name = next(
                (
                    variable_option["label"]
                    for variable_option in compared_table_meta.get("variables", [])
                    if str(variable_option["value"]) == str(correlation_record.compared_variable)
                ),
                str(correlation_record.compared_variable),
            )

            comp_demographic_name = correlation_record.compared_demographic or ""
            comp_option_name = ""

            # Resolve the compared classification/category label if applicable
            if correlation_record.compared_demographic and correlation_record.compared_category:
                comp_option_name = next(
                    (
                        classification_option["label"]
                        for classification_option in compared_table_meta.get("classification_members", {}).get(correlation_record.compared_demographic, [])
                        if str(classification_option["value"]) == str(correlation_record.compared_category)
                    ),
                    str(correlation_record.compared_category),
                )

            correlations.append({
                "score": correlation_record.score,
                "compared_variable": correlation_record.compared_variable,
                "compared_table": correlation_record.compared_table,
                "compared_demographic": correlation_record.compared_demographic,
                "compared_category": correlation_record.compared_category,
                "compared_variable_name": compared_variable_name,
                "compared_table_name": compared_table_meta.get("table_name", str(correlation_record.compared_table)),
                "compared_demographic_name": comp_demographic_name,
                "compared_category_name": comp_option_name,
            })

        # Sort by correlation strength, strongest first
        correlations.sort(key=lambda correlation_item: abs(correlation_item["score"] or 0), reverse=True)

        result.append({
            "id": saved_variable.id,
            "label": saved_variable.label,
            "table": saved_variable.table_id,
            "variable": saved_variable.variable_id,
            "variable_name": variable_name,
            "table_name": table_meta.get("table_name", str(saved_variable.table_id)),
            "demographic_name": demographic_name,
            "category_name": selected_option_name,
            "correlations": correlations,
        })

    return jsonify(result)


@app.route("/map-variables")
@login_required
def map_variables_page():
    """
    Render the saved map variables page for the logged-in user
    """
    return render_template("map_variables.html")


if __name__ == "__main__":
    """
    Application entry point for local development

    Ensures all database tables exist, then starts the Flask development server
    """
    with app.app_context():
        db.create_all()
    app.run(debug=True)