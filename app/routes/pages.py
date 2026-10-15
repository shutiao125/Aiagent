"""页面路由（静态入口；其余静态资源由 Flask static 直接提供）。"""
from __future__ import annotations

from flask import Blueprint, current_app

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return current_app.send_static_file("index.html")


@bp.get("/student")
def student():
    return current_app.send_static_file("student.html")
