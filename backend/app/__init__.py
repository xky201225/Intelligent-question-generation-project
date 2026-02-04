import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from app.config import Config
from app.db import close_session, init_db


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["EXPORT_DIR"], exist_ok=True)

    init_db(app)
    app.teardown_appcontext(close_session)

    from app.api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.errorhandler(Exception)
    def handle_exception(err: Exception):
        code = getattr(err, "code", 500)
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), code

    return app
