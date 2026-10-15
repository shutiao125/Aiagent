"""专业课程管理路由：仅做参数提取与声明式服务绑定。"""
from __future__ import annotations

from flask import Blueprint, request

from ..response import ok
from ..services import Services

bp = Blueprint("courses", __name__, url_prefix="/api/courses")


@bp.get("")
def list_courses():
    return ok(Services.courses.list_courses())


@bp.post("")
def create_course():
    return ok(Services.courses.create_course(request.get_json(silent=True) or {}))


@bp.put("/<int:course_id>")
def update_course(course_id: int):
    return ok(Services.courses.update_course(course_id, request.get_json(silent=True) or {}))


@bp.delete("/<int:course_id>")
def delete_course(course_id: int):
    Services.courses.delete_course(course_id)
    return ok(None, message="删除成功")
