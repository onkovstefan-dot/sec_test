from flask import Blueprint, jsonify
from models.submissions_flat import SubmissionsFlat
from db import SessionLocal
import os

api_bp = Blueprint('api', __name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sec.db')

# @api_bp.route('/')
# def hello():
#     return 'Hello, world!'

@api_bp.route('/', methods=['GET'])
# @api_bp.route('/', methods=['GET'])

def get_submissions_flat_sample():
    session = SessionLocal()
    records = session.query(SubmissionsFlat).limit(1).all()
    result = [
        {column: getattr(record, column) for column in SubmissionsFlat.__table__.columns.keys()}
        for record in records
    ]
    session.close()
    return jsonify(result)
