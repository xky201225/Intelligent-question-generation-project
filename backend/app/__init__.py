import os

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired

from app.config import Config
from app.db import close_session, init_db
from app.api.auth import verify_token


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["EXPORT_DIR"], exist_ok=True)

    init_db(app)
    app.teardown_appcontext(close_session)

    from app.api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.before_request
    def require_login():
        path = request.path or ""
        if request.method == "OPTIONS":
            return None
        if not path.startswith("/api"):
            return None
        if path in ["/api/health", "/api/auth/login", "/api/auth/register", "/api/auth/captcha", "/api/auth/stats"]:
            return None

        token = None
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
        token = token or request.args.get("token", type=str)
        if not token:
            return jsonify({"error": {"message": "未登录", "type": "Unauthorized"}}), 401

        try:
            data = verify_token(token)
        except SignatureExpired:
            return jsonify({"error": {"message": "登录已过期", "type": "Unauthorized"}}), 401
        except BadSignature:
            return jsonify({"error": {"message": "无效登录", "type": "Unauthorized"}}), 401

        g.auth = data
        return None

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.errorhandler(Exception)
    def handle_exception(err: Exception):
        code = getattr(err, "code", 500)
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), code

    return app
