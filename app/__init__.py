import os
import secrets
import time

import jwt
from dotenv import load_dotenv
from flask import Flask, current_app, g, jsonify, request
from flask_limiter import Limiter
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


def _rate_limit_key():
    header = request.headers.get('Authorization', '')
    token = None
    if header.startswith('Bearer '):
        token = header.replace('Bearer ', '', 1).strip()
    if not token:
        token = request.cookies.get('insighta_access_token')
    if not token:
        return request.remote_addr or 'anonymous'
    try:
        payload = jwt.decode(token, current_app.config.get('JWT_SECRET', ''), algorithms=['HS256'])
        return payload.get('sub') or (request.remote_addr or 'anonymous')
    except jwt.InvalidTokenError:
        return request.remote_addr or 'anonymous'

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=_rate_limit_key, default_limits=[])


def create_app(config_override=None):
    load_dotenv()

    app = Flask(__name__)

    if config_override:
        app.config.update(config_override)
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
            'DATABASE_URL',
            'postgresql://postgres:postgres@localhost:5432/hng_data'
        )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = app.config.get('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    app.config['API_TIMEOUT'] = int(app.config.get('API_TIMEOUT', os.getenv('API_TIMEOUT', 10)))
    app.config['JWT_SECRET'] = app.config.get('JWT_SECRET', os.getenv('JWT_SECRET', secrets.token_hex(32)))
    app.config['GITHUB_CLIENT_ID'] = app.config.get('GITHUB_CLIENT_ID', os.getenv('GITHUB_CLIENT_ID', ''))
    app.config['GITHUB_CLIENT_SECRET'] = app.config.get('GITHUB_CLIENT_SECRET', os.getenv('GITHUB_CLIENT_SECRET', ''))
    app.config['WEB_POST_LOGIN_REDIRECT'] = app.config.get(
        'WEB_POST_LOGIN_REDIRECT',
        os.getenv('WEB_POST_LOGIN_REDIRECT', 'http://localhost:3000/dashboard'),
    )
    app.config['WEB_CALLBACK_URL'] = app.config.get(
        'WEB_CALLBACK_URL',
        os.getenv('WEB_CALLBACK_URL', 'http://localhost:5000/auth/github/callback?mode=cookie'),
    )
    app.config['COOKIE_SECURE'] = app.config.get('COOKIE_SECURE', os.getenv('COOKIE_SECURE', 'false').lower() == 'true')
    _cors = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:5174,http://localhost:3000')
    app.config['CORS_ORIGINS'] = [o.strip() for o in _cors.split(',') if o.strip()]
    app.config['ADMIN_GITHUB_IDS'] = os.getenv('ADMIN_GITHUB_IDS', '')

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    from app.auth_routes import auth_bp
    from app.cli import register_cli_commands
    from app.routes import api_bp
    register_cli_commands(app)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        allowed = app.config.get('CORS_ORIGINS') or []
        if origin and origin in allowed:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,PATCH,DELETE,OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-API-Version,X-CSRF-Token'
        return response

    @app.before_request
    def handle_preflight():
        g.request_started_at = time.perf_counter()
        if request.method == 'OPTIONS':
            return '', 204

    @app.before_request
    def enforce_github_config():
        def local_error(message, status_code):
            return jsonify({'status': 'error', 'message': message}), status_code

        if request.path.startswith('/auth/github') and (
            not app.config['GITHUB_CLIENT_ID'] or not app.config['GITHUB_CLIENT_SECRET']
        ):
            return local_error('GitHub OAuth is not configured', 500)

    @app.route('/health')
    def health():
        return {'status': 'healthy'}

    @app.after_request
    def log_request(response):
        started_at = getattr(g, 'request_started_at', None)
        elapsed_ms = 0.0
        if started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
        app.logger.info(
            'request method=%s endpoint=%s status=%s response_time_ms=%.2f',
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    return app
