import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from backend.config import Config
from backend.database import init_default_admin

security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)
_handler = logging.FileHandler(os.path.join(Config.PROJECT_ROOT, "security.log"))
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
security_logger.addHandler(_handler)

app_logger = logging.getLogger("app")
app_logger.setLevel(logging.INFO)
_app_handler = logging.FileHandler(os.path.join(Config.PROJECT_ROOT, "app.log"))
_app_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
app_logger.addHandler(_app_handler)

if not Config.SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in .env")

limiter = Limiter(key_func=get_remote_address)


def create_app():
    app = Flask(
        __name__,
        static_folder=Config.FRONTEND_FOLDER,
        static_url_path="",
    )
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

    CORS(app, resources={r"/api/*": {"origins": [
        "http://localhost:5001",
        "http://127.0.0.1:5001",
    ], "supports_credentials": True}})

    limiter.init_app(app)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.before_request
    def log_request():
        if request.endpoint and request.endpoint != "static":
            app_logger.info(f"{request.remote_addr} {request.method} {request.path}")

    from backend.routes.auth import auth_bp
    from backend.routes.cameras import cameras_bp
    from backend.routes.violations import violations_bp
    from backend.routes.reports import reports_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(cameras_bp, url_prefix="/api/cameras")
    app.register_blueprint(violations_bp, url_prefix="/api/violations")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        security_logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(429)
    def rate_limit(e):
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

    @app.route("/")
    def serve_index():
        return send_from_directory(Config.FRONTEND_FOLDER, "index.html")

    @app.route("/pages/<path:filename>")
    def serve_page(filename):
        return send_from_directory(os.path.join(Config.FRONTEND_FOLDER, "pages"), filename)

    @app.route("/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(os.path.join(Config.FRONTEND_FOLDER, "css"), filename)

    @app.route("/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(os.path.join(Config.FRONTEND_FOLDER, "js"), filename)

    @app.route("/models/<path:filename>")
    def serve_model(filename):
        return send_from_directory(os.path.join(Config.BASE_DIR, "..", "models"), filename)

    @app.route("/videos/<path:filename>")
    def serve_video(filename):
        return send_from_directory(os.path.join(Config.BASE_DIR, "..", "videos"), filename)

    return app


if __name__ == "__main__":
    try:
        init_default_admin()
    except Exception as e:
        app_logger.error(f"Could not init default user: {e}")

    app = create_app()
    app_logger.info("Starting server on http://0.0.0.0:5001")
    security_logger.info("Server started")
    app.run(host="0.0.0.0", port=5001, debug=False)
