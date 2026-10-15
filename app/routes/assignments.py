"""作业习题管理 + AI 生成路由：仅做参数提取与声明式服务绑定。"""
from __future__ import annotations

from flask import Blueprint, request

from ..response import ok
from ..services import Services

bp = Blueprint("assignments", __name__, url_prefix="/api")


@bp.get("/dashboard")
def dashboard():
    return ok(Services.assignments.dashboard())


@bp.get("/assignments")
def list_assignments():
    args = request.args
    return ok(Services.assignments.list_assignments(
        class_id=args.get("class_id"),
        course_id=args.get("course_id"),
        keyword=args.get("keyword"),
    ))


@bp.post("/assignments")
def create_assignment():
    return ok(Services.assignments.create_assignment(request.get_json(silent=True) or {}))


@bp.post("/generate-assignment")
def generate_assignment():
    result = Services.generation.generate(request.get_json(silent=True) or {})
    return ok(result, message=f"已生成 {result['question_count']} 道习题")


@bp.get("/assignments/<int:assignment_id>")
def get_assignment(assignment_id: int):
    return ok(Services.assignments.get_assignment_detail(assignment_id))


@bp.put("/assignments/<int:assignment_id>")
def update_assignment(assignment_id: int):
    return ok(Services.assignments.update_assignment(
        assignment_id, request.get_json(silent=True) or {}
    ))


@bp.delete("/assignments/<int:assignment_id>")
def delete_assignment(assignment_id: int):
    Services.assignments.delete_assignment(assignment_id)
    return ok(None, message="删除成功")


# ---------- 习题 ----------
@bp.post("/assignments/<int:assignment_id>/questions")
def add_question(assignment_id: int):
    return ok(Services.assignments.add_question(
        assignment_id, request.get_json(silent=True) or {}
    ))


@bp.put("/questions/<int:question_id>")
def update_question(question_id: int):
    return ok(Services.assignments.update_question(
        question_id, request.get_json(silent=True) or {}
    ))


@bp.delete("/questions/<int:question_id>")
def delete_question(question_id: int):
    Services.assignments.delete_question(question_id)
    return ok(None, message="删除成功")
