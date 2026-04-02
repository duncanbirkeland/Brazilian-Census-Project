from datetime import datetime  # Timestamp support for created_at fields.

from flask_sqlalchemy import SQLAlchemy  # Flask integration for SQLAlchemy ORM.
from werkzeug.security import generate_password_hash, check_password_hash  # Password hashing utilities.

# Shared SQLAlchemy database instance, initialized in app.py with db.init_app(app).
db = SQLAlchemy()


class User(db.Model):
    """
    User account model.

    Stores login credentials and account creation time.
    Passwords are never stored in plain text; only a hashed version is saved.
    """

    # Primary key for the user record.
    id = db.Column(db.Integer, primary_key=True)

    # User email address.
    # - unique=True prevents duplicate accounts with the same email
    # - nullable=False makes this field required
    # - index=True improves lookup speed for login queries
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Securely hashed password string.
    password_hash = db.Column(db.String(255), nullable=False)

    # UTC timestamp for when the account was created.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """
        Hash and store a user's password.

        Args:
            password (str): Plain-text password provided by the user.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verify a plain-text password against the stored password hash.

        Args:
            password (str): Plain-text password to verify.

        Returns:
            bool: True if the password matches, otherwise False.
        """
        return check_password_hash(self.password_hash, password)


class MapVariable(db.Model):
    """
    A variable saved by a user from the map interface.

    This stores the selected SIDRA table/variable combination and any optional
    demographic/classification metadata, along with a user-facing label.
    """

    # Primary key for the saved variable.
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key linking this saved variable to the owning user.
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # SIDRA table identifier.
    table_id = db.Column(db.String(50))

    # SIDRA variable identifier.
    variable_id = db.Column(db.String(50))

    # Optional demographic dimension selected by the user.
    demographic = db.Column(db.String(255))

    # Optional classification/category value selected by the user.
    classification = db.Column(db.String(255))

    # Friendly display label shown in the UI.
    label = db.Column(db.String(255))

    # UTC timestamp for when this variable was saved.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One-to-many relationship to saved correlations for this map variable.
    # cascade="all, delete-orphan" ensures child correlation records are deleted
    # if the parent MapVariable is removed.
    correlations = db.relationship(
        "Correlation",
        backref="map_variable",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Correlation(db.Model):
    """
    Correlation result linked to a saved map variable.

    Stores the compared SIDRA selection and the computed Pearson correlation
    score against the parent MapVariable.
    """

    # Primary key for the correlation record.
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key linking this correlation to the saved map variable it belongs to.
    map_variable_id = db.Column(
        db.Integer,
        db.ForeignKey("map_variable.id"),
        nullable=False
    )

    # SIDRA table ID for the compared variable.
    compared_table = db.Column(db.String(50))

    # SIDRA variable ID for the compared variable.
    compared_variable = db.Column(db.String(50))

    # Optional demographic used in the compared selection.
    compared_demographic = db.Column(db.String(255))

    # Optional category/classification used in the compared selection.
    compared_category = db.Column(db.String(255))

    # Computed Pearson correlation score.
    score = db.Column(db.Float)

    # UTC timestamp for when the correlation was stored.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)