from flask import Blueprint, jsonify
from models.submissions_flat import SubmissionsFlat
from db import SessionLocal

api_bp = Blueprint("api", __name__)


# @api_bp.route('/')
# def hello():
#     return 'Hello, world!'


@api_bp.route("/", methods=["GET"])
def get_submissions_flat_sample():
    session = SessionLocal()
    records = session.query(SubmissionsFlat).limit(1).all()
    columns = SubmissionsFlat.__table__.columns.keys()
    result = [
        {column: getattr(record, column) for column in columns} for record in records
    ]
    session.close()
    return jsonify(result)
