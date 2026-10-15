"""统一路由注册：所有 Blueprint 仅在此处集中挂载到应用。"""
from __future__ import annotations

from flask import Flask

from .assignments import bp as assignments_bp
from .classes import bp as classes_bp
from .conversations import bp as conversations_bp
from .courses import bp as courses_bp
from .grading import bp as grading_bp
from .health import bp as health_bp
from .messages import bp as messages_bp
from .pages import bp as pages_bp

_ALL_BLUEPRINTS = (
    pages_bp,
    health_bp,
    classes_bp,
    courses_bp,
    assignments_bp,
    grading_bp,
    conversations_bp,
    messages_bp,
)


def register_routes(app: Flask) -> None:
    for blueprint in _ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)
