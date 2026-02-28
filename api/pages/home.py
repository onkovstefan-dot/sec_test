from flask import Blueprint, render_template

home_bp = Blueprint("home", __name__)


@home_bp.route("/", methods=["GET"])
def home_page():
    """Home page: choose between CIK data explorer and admin tools."""
    return render_template("pages/home.html"), 200
