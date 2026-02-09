from flask import Blueprint

from app.api.ai import ai_bp
from app.api.answer_sheets import answer_sheets_bp, answer_styles_bp
from app.api.auth import auth_bp
from app.api.dicts import dicts_bp
from app.api.papers import papers_bp
from app.api.questions import questions_bp
from app.api.textbooks import textbooks_bp
from app.api.dashboard import dashboard_bp

api_bp = Blueprint("api", __name__)
api_bp.register_blueprint(auth_bp, url_prefix="/auth")
api_bp.register_blueprint(dicts_bp, url_prefix="/dicts")
api_bp.register_blueprint(textbooks_bp, url_prefix="/textbooks")
api_bp.register_blueprint(questions_bp, url_prefix="/questions")
api_bp.register_blueprint(ai_bp, url_prefix="/ai")
api_bp.register_blueprint(papers_bp, url_prefix="/papers")
api_bp.register_blueprint(answer_styles_bp, url_prefix="/answer-styles")
api_bp.register_blueprint(answer_sheets_bp, url_prefix="/answer-sheets")
api_bp.register_blueprint(dashboard_bp, url_prefix="/dashboard")
