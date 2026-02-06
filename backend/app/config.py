import os


class Config:
    APP_ENV = os.getenv("APP_ENV", "dev")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    AUTH_TOKEN_SALT = os.getenv("AUTH_TOKEN_SALT", "auth-token")
    AUTH_TOKEN_EXPIRES_SECONDS = int(os.getenv("AUTH_TOKEN_EXPIRES_SECONDS", str(7 * 24 * 3600)))
    AUTH_INVITATION_CODE = os.getenv("AUTH_INVITATION_CODE", "")

    MYSQL_HOST = os.getenv("MYSQL_HOST", "8.136.42.57")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_DB = os.getenv("MYSQL_DB", "exam_system-v3")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "201225")

    SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "0") == "1"

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads")))
    EXPORT_DIR = os.getenv("EXPORT_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exports")))
