from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

db = SQLAlchemy()
migrate = Migrate()


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
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['API_TIMEOUT'] = int(os.getenv('API_TIMEOUT', 10))

    db.init_app(app)
    migrate.init_app(app, db)

    from app.cli import register_cli_commands
    from app.routes import api_bp
    register_cli_commands(app)
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,PATCH,DELETE,OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        return response

    @app.before_request
    def handle_preflight():
        if request.method == 'OPTIONS':
            return '', 204

    @app.route('/health')
    def health():
        return {'status': 'healthy'}

    return app
