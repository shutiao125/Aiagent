"""学生作答提交 + 教师批改路由。"""
from __future__ import annotations

from flask import Blueprint, request

from ..response import ok
from ..services import Services

bp = Blueprint("grading", __name__, url_prefix="/api")


# ---------- 学生端（免登录） ----------
@bp.get("/student/assignments")
def student_assignments():
    return ok(Services.submissions.list_published_assignments())


@bp.get("/student/assignments/<int:assignment_id>/paper")
def student_paper(assignment_id: int):
    return ok(Services.submissions.get_paper(assignment_id))


@bp.post("/student/assignments/<int:assignment_id>/submit")
def student_submit(assignment_id: int):
    result = Services.submissions.submit(
        assignment_id, request.get_json(silent=True) or {}
    )
    return ok(result, message="提交成功")


# ---------- 教师端 ----------
@bp.get("/grading/pending-count")
def grading_pending_count():
    return ok({"count": Services.submissions.pending_count()})


@bp.get("/grading/submissions")
def grading_list():
    args = request.args
    return ok(Services.submissions.list_grading(
        status=args.get("status"),
        class_id=args.get("class_id"),
        assignment_id=args.get("assignment_id"),
        keyword=args.get("keyword"),
    ))


@bp.get("/grading/submissions/<int:submission_id>")
def grading_detail(submission_id: int):
    return ok(Services.submissions.get_detail(submission_id))


@bp.post("/grading/submissions/<int:submission_id>/grade")
def grading_save(submission_id: int):
    return ok(Services.submissions.save_teacher_grade(
        submission_id, request.get_json(silent=True) or {}
    ), message="批改已保存")
