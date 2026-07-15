from pathlib import Path

from flask import Flask

from app.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app():
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.config.from_object(Config)

    from app.routes import bp
    app.register_blueprint(bp)

    return app
