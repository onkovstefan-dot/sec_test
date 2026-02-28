from flask import Flask
from api.routes import api_bp
from db import engine, Base

app = Flask(__name__)
app.register_blueprint(api_bp)

# Create all tables
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    app.run(debug=True)
