from flask import Flask, render_template_string
from api.routes import api_bp
from db import engine
from models.submissions_flat import SubmissionsFlat
from models.companyfacts_flat import *  # Add other models as needed
from db import Base

app = Flask(__name__)
app.register_blueprint(api_bp)

# Create all tables
Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    app.run(debug=True)
