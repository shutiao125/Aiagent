"""学生提交与教师批改业务服务。"""
from __future__ import annotations

import json
import logging

from ..db import db_cursor
from ..models.assignment_dao import AssignmentDao
from ..models.question_dao import QuestionDao
from ..models.submission_dao import SubmissionDao
from ..response import BizError, ErrorCode
from ..utils.serialization import to_jsonable
from .grading_service import CHOICE_TYPES, GradingService

logger = logging.getLogger(__name__)

QUESTION_TYPE_LABELS = {
    "single": "单选题", "multiple": "多选题", "judge": "判断题",
    "fill": "填空题", "short": "简答题",
}


def _load_options(row: dict):
    raw = row.get("options_json")
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
    return raw if isinstance(raw, list) else None


class SubmissionService:
    def __init__(self):
        self.sub_dao = SubmissionDao()
        self.assignment_dao = AssignmentDao()
        self.question_dao = QuestionDao()
        self.grading = GradingService()

    # ============ 学生端 ============
    def list_published_assignments(self) -> list[dict]:
        return [to_jsonable(r) for r in self.assignment_dao.list_page(limit=500)]

    def get_paper(self, assignment_id: int) -> dict:
        """学生试卷：下发题目与选项，但剥离参考答案与解析。"""
        assignment = self.assignment_dao.get(assignment_id)
        if assignment is None:
            raise BizError("作业不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        questions = []
        for q in self.question_dao.list_by_assignment(assignment_id):
            questions.append({
                "id": q["id"], "seq": q["seq"], "type": q["type"],
                "type_label": QUESTION_TYPE_LABELS.get(q["type"], q["type"]),
                "stem": q["stem"], "options": _load_options(q),
                "score": q["score"],
                # 注意：不下发 answer / analysis
            })
        return {
            "id": assignment["id"], "title": assignment["title"],
            "class_id": assignment["class_id"],
            "class_name": assignment["class_name"],
            "course_id": assignment["course_id"],
            "course_name": assignment["course_name"],
            "difficulty": assignment["difficulty"],
            "requirement": assignment["requirement"],
            "questions": questions,
            "max_score": sum(q["score"] for q in questions),
        }

    def submit(self, assignment_id: int, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise BizError("请求体格式错误")
        assignment = self.assignment_dao.get(assignment_id)
        if assignment is None:
            raise BizError("作业不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)

        student_name = (payload.get("student_name") or "").strip()
        student_no = (payload.get("student_no") or "").strip()
        if not student_name:
            raise BizError("请填写学生姓名")
        if len(student_name) > 50:
            raise BizError("学生姓名不能超过 50 字")
        if not student_no:
            raise BizError("请填写学号")
        if len(student_no) > 30:
            raise BizError("学号不能超过 30 字")
        if self.sub_dao.exists_student(assignment_id, student_no):
            raise BizError("该学号已提交过本次作业，不能重复提交")

        raw_answers = payload.get("answers")
        if not isinstance(raw_answers, list):
            raise BizError("作答数据格式错误")

        questions = self.question_dao.list_by_assignment(assignment_id)
        if not questions:
            raise BizError("作业还没有题目，暂不能提交")
        qmap = {q["id"]: q for q in questions}
        resp_map: dict[int, str] = {}
        for item in raw_answers:
            if not isinstance(item, dict):
                continue
            try:
                qid = int(item.get("question_id"))
            except (TypeError, ValueError):
                continue
            resp_map[qid] = str(item.get("response") or "").strip()[:5000]

        max_score = sum(q["score"] for q in questions)

        # 阶段一：落提交与作答明细
        with db_cursor(commit=True) as cur:
            submission_id = self.sub_dao.insert(
                assignment_id, student_name, student_no, max_score, cur=cur
            )
            answer_ids: dict[int, int] = {}
            for q in questions:
                aid = self.sub_dao.insert_answer(
                    submission_id, q["id"], q["seq"], q["type"],
                    resp_map.get(q["id"], ""), cur=cur
                )
                answer_ids[q["id"]] = aid

        # 阶段二：客观题自动批改（失败不影响提交，保留为待批）
        fill_items: list[dict] = []
        for q in questions:
            response = resp_map.get(q["id"], "")
            if q["type"] in CHOICE_TYPES:
                result = self.grading.grade_choice(q, response)
                self.sub_dao.apply_ai_grade(
                    answer_ids[q["id"]],
                    None if result is None else result["is_correct"],
                    None if result is None else result["score"],
                    "客观题缺少标准答案，请老师人工批改。" if result is None else result["comment"],
                )
            elif q["type"] == "fill":
                fill_items.append({
                    "question_id": q["id"],
                    "stem": q["stem"],
                    "reference": q["answer"],
                    "response": response,
                    "score": q["score"],
                })

        if fill_items:
            try:
                fill_results = self.grading.grade_fill_batch(fill_items)
            except Exception as exc:  # noqa: BLE001 — 兜底：全部留待人工
                logger.exception("AI 填空批改异常：%s", exc)
                fill_results = {
                    it["question_id"]: {
                        "is_correct": None, "score": None,
                        "comment": "AI 批改异常，请老师人工批改。",
                    }
                    for it in fill_items
                }
            for qid, result in fill_results.items():
                self.sub_dao.apply_ai_grade(
                    answer_ids[qid], result["is_correct"], result["score"],
                    result["comment"],
                )

        # 阶段三：汇总状态与总分
        status, total = self._recalculate(submission_id)
        return {
            "submission_id": submission_id,
            "status": status,
            "total_score": total,
            "max_score": max_score,
            "has_subjective": any(q["type"] == "short" for q in questions),
        }

    # ============ 教师端 ============
    def list_grading(self, status=None, class_id=None, assignment_id=None,
                     keyword=None) -> list[dict]:
        rows = self.sub_dao.list_(
            status=status,
            class_id=_opt_int(class_id),
            assignment_id=_opt_int(assignment_id),
            keyword=(keyword or "").strip() or None,
        )
        result = []
        for r in rows:
            item = to_jsonable(r)
            item["status_label"] = "待批改" if r["status"] == "pending" else "已批改"
            result.append(item)
        return result

    def pending_count(self) -> int:
        return self.sub_dao.count_pending()

    def get_detail(self, submission_id: int) -> dict:
        sub = self.sub_dao.get_with_assignment(submission_id)
        if sub is None:
            raise BizError("提交记录不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        sub = to_jsonable(sub)
        answers = []
        for row in self.sub_dao.list_answers_with_questions(submission_id):
            item = to_jsonable(row)
            item["options"] = _load_options(row)
            item["type_label"] = QUESTION_TYPE_LABELS.get(row["type"], row["type"])
            item.pop("options_json", None)
            answers.append(item)
        sub["answers"] = answers
        return sub

    def save_teacher_grade(self, submission_id: int, payload: dict) -> dict:
        sub = self.sub_dao.get(submission_id)
        if sub is None:
            raise BizError("提交记录不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        grades = payload.get("grades") if isinstance(payload, dict) else None
        if not isinstance(grades, list) or not grades:
            raise BizError("批改数据不能为空")

        existing = {
            row["answer_id"]: row for row in
            self.sub_dao.list_answers_with_questions(submission_id)
        }
        with db_cursor(commit=True) as cur:
            for g in grades:
                if not isinstance(g, dict):
                    continue
                try:
                    answer_id = int(g.get("answer_id"))
                except (TypeError, ValueError):
                    raise BizError("批改数据格式错误")
                row = existing.get(answer_id)
                if row is None:
                    raise BizError("存在不属于本次提交的题目批改")
                try:
                    score = int(g.get("score"))
                except (TypeError, ValueError):
                    raise BizError("请为每道题填写有效得分")
                if score < 0 or score > row["max_score"]:
                    raise BizError(f"第 {row['seq']} 题得分需在 0-{row['max_score']} 之间")
                is_correct = 1 if g.get("is_correct", score > 0) else 0
                comment = str(g.get("comment") or "").strip()[:500]
                self.sub_dao.update_grade(
                    answer_id, is_correct, score, comment, cur=cur
                )

        status, total = self._recalculate(submission_id)
        return self.get_detail(submission_id)

    # ---------- 汇总 ----------
    def _recalculate(self, submission_id: int) -> tuple[str, int]:
        """状态与总分统一由作答明细派生：仍有未批→pending，否则 graded。"""
        summary = self.sub_dao.score_summary(submission_id)
        if summary["pending_cnt"] and summary["pending_cnt"] > 0:
            status, total = "pending", int(summary["scored_sum"])
        else:
            status, total = "graded", int(summary["scored_sum"])
        self.sub_dao.finalize(submission_id, status, total)
        return status, total


def _opt_int(value):
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
