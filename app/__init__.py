from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.ensure_ascii = False

    db.init_app(app)

    # Import and register blueprints
    from app.routes.main_routes import bp as main_bp
    app.register_blueprint(main_bp)

    @app.after_request
    def _add_cors_headers(response):
        response.headers.setdefault('Access-Control-Allow-Origin', '*')
        response.headers.setdefault('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS')
        response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response

    return app
