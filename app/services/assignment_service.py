"""作业与习题业务服务。"""
from __future__ import annotations

import json

from ..db import db_cursor
from ..models.assignment_dao import AssignmentDao
from ..models.class_dao import ClassDao
from ..models.course_dao import CourseDao
from ..models.question_dao import QuestionDao
from ..response import BizError, ErrorCode
from ..utils.serialization import to_jsonable

QUESTION_TYPES = ("single", "multiple", "judge", "fill", "short")
CHOICE_TYPES = ("single", "multiple", "judge")
DIFFICULTY_MAP = {1: "简单", 2: "中等", 3: "困难"}


class AssignmentService:
    def __init__(self):
        self.assignment_dao = AssignmentDao()
        self.question_dao = QuestionDao()
        self.class_dao = ClassDao()
        self.course_dao = CourseDao()

    # ---------- 首页统计 ----------
    def dashboard(self) -> dict:
        from ..models.submission_dao import SubmissionDao
        return {
            "class_count": self.class_dao.count_all(),
            "course_count": self.course_dao.count_all(),
            "assignment_count": self.assignment_dao.count_all(),
            "question_count": self.question_dao.count_all(),
            "pending_submission_count": SubmissionDao().count_pending(),
            "recent_assignments": [
                to_jsonable(r) for r in self.assignment_dao.list_recent(5)
            ],
        }

    # ---------- 作业 ----------
    def list_assignments(self, class_id=None, course_id=None, keyword=None) -> list[dict]:
        rows = self.assignment_dao.list_page(
            _opt_int(class_id), _opt_int(course_id),
            (keyword or "").strip() or None,
        )
        result = []
        for row in rows:
            item = to_jsonable(row)
            item["difficulty_label"] = DIFFICULTY_MAP.get(item["difficulty"], "中等")
            result.append(item)
        return result

    def get_assignment_detail(self, assignment_id: int) -> dict:
        assignment = self.assignment_dao.get(assignment_id)
        if assignment is None:
            raise BizError("作业不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        assignment = to_jsonable(assignment)
        assignment["difficulty_label"] = DIFFICULTY_MAP.get(assignment["difficulty"], "中等")
        assignment["questions"] = [
            self._serialize_question(q) for q in self.question_dao.list_by_assignment(assignment_id)
        ]
        return assignment

    def create_assignment(self, payload: dict) -> dict:
        title, class_id, course_id, difficulty, requirement = self._read_assignment_payload(payload)
        self._ensure_refs_exist(class_id, course_id)
        questions = self._read_questions(payload.get("questions"), allow_empty=True)
        with db_cursor(commit=True) as cur:
            assignment_id = self.assignment_dao.insert(
                title, class_id, course_id, difficulty, requirement, "manual", cur=cur
            )
            if questions:
                self.question_dao.batch_insert(assignment_id, questions, cur=cur)
        return self.get_assignment_detail(assignment_id)

    def update_assignment(self, assignment_id: int, payload: dict) -> dict:
        if self.assignment_dao.get(assignment_id) is None:
            raise BizError("作业不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        title, class_id, course_id, difficulty, requirement = self._read_assignment_payload(payload)
        self._ensure_refs_exist(class_id, course_id)
        self.assignment_dao.update(
            assignment_id, title, class_id, course_id, difficulty, requirement
        )
        return self.get_assignment_detail(assignment_id)

    def delete_assignment(self, assignment_id: int) -> None:
        if self.assignment_dao.get(assignment_id) is None:
            raise BizError("作业不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        self.assignment_dao.soft_delete(assignment_id)

    # ---------- 习题 ----------
    def add_question(self, assignment_id: int, payload: dict) -> dict:
        if self.assignment_dao.get(assignment_id) is None:
            raise BizError("作业不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        question = self._normalize_question(payload)
        seq = self.question_dao.max_seq(assignment_id) + 1
        question_id = self.question_dao.insert(
            assignment_id, seq, question["type"], question["stem"],
            question.get("options"), question["answer"], question.get("analysis", ""),
            question["score"],
        )
        return self._serialize_question(self.question_dao.get(question_id))

    def update_question(self, question_id: int, payload: dict) -> dict:
        row = self.question_dao.get(question_id)
        if row is None:
            raise BizError("习题不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        question = self._normalize_question(payload)
        self.question_dao.update(
            question_id, question["type"], question["stem"],
            question.get("options"), question["answer"], question.get("analysis", ""),
            question["score"],
        )
        return self._serialize_question(self.question_dao.get(question_id))

    def delete_question(self, question_id: int) -> None:
        if self.question_dao.delete(question_id) == 0:
            raise BizError("习题不存在", code=ErrorCode.NOT_FOUND, http_status=404)

    # ---------- 内部工具 ----------
    def _ensure_refs_exist(self, class_id: int, course_id: int) -> None:
        if self.class_dao.get(class_id) is None:
            raise BizError("所选班级不存在，请重新选择")
        if self.course_dao.get(course_id) is None:
            raise BizError("所选课程不存在，请重新选择")

    @staticmethod
    def _read_assignment_payload(payload: dict) -> tuple[str, int, int, int, str]:
        if not isinstance(payload, dict):
            raise BizError("请求体格式错误")
        title = (payload.get("title") or "").strip()
        if not title:
            raise BizError("作业标题不能为空")
        if len(title) > 150:
            raise BizError("作业标题不能超过 150 字")
        try:
            class_id = int(payload.get("class_id"))
            course_id = int(payload.get("course_id"))
        except (TypeError, ValueError):
            raise BizError("请选择有效的班级与课程")
        try:
            difficulty = int(payload.get("difficulty", 2))
        except (TypeError, ValueError):
            difficulty = 2
        if difficulty not in (1, 2, 3):
            raise BizError("难度取值无效")
        requirement = (payload.get("requirement") or "").strip()
        return title, class_id, course_id, difficulty, requirement

    def _read_questions(self, raw, allow_empty: bool) -> list[dict]:
        if raw is None:
            return [] if allow_empty else []
        if not isinstance(raw, list):
            raise BizError("习题数据格式错误，应为数组")
        questions = [self._normalize_question(item) for item in raw]
        if not allow_empty and not questions:
            raise BizError("至少需要一道习题")
        return questions

    @staticmethod
    def _normalize_question(item: dict) -> dict:
        if not isinstance(item, dict):
            raise BizError("习题项格式错误")
        qtype = (item.get("type") or "").strip()
        if qtype not in QUESTION_TYPES:
            raise BizError(f"不支持的题型：{qtype}")
        stem = (item.get("stem") or "").strip()
        if not stem:
            raise BizError("题干不能为空")
        answer = (item.get("answer") or "").strip()
        if not answer:
            raise BizError("参考答案不能为空")
        analysis = (item.get("analysis") or "").strip()
        try:
            score = int(item.get("score", 5))
        except (TypeError, ValueError):
            score = 5
        if score < 1 or score > 100:
            raise BizError("题目分值需在 1-100 之间")

        options = None
        if qtype in CHOICE_TYPES:
            options = _normalize_options(item.get("options"), qtype)
            # 校验答案键在选项范围内
            valid_keys = {opt["key"] for opt in options}
            given_keys = [ch.upper() for ch in answer.replace(",", "").replace("，", "")]
            if not given_keys or any(k not in valid_keys for k in given_keys):
                raise BizError(f"题目「{stem[:20]}」的答案不在选项范围内")
            answer = "".join(dict.fromkeys(given_keys))  # 去重保序
        return {
            "type": qtype, "stem": stem, "options": options,
            "answer": answer, "analysis": analysis, "score": score,
        }

    @staticmethod
    def _serialize_question(row: dict) -> dict:
        row = to_jsonable(row)
        raw = row.get("options_json")
        if isinstance(raw, str) and raw.strip():
            try:
                row["options"] = json.loads(raw)
            except (ValueError, TypeError):
                row["options"] = None
        else:
            row["options"] = raw if isinstance(raw, list) else None
        row.pop("options_json", None)
        row["type_label"] = QUESTION_TYPE_LABELS.get(row["type"], row["type"])
        return row


QUESTION_TYPE_LABELS = {
    "single": "单选题",
    "multiple": "多选题",
    "judge": "判断题",
    "fill": "填空题",
    "short": "简答题",
}


def _normalize_options(raw_options, qtype: str) -> list[dict]:
    """判断题缺省选项自动补 正确/错误；选择类选项统一为 [{key, content}]。"""
    if qtype == "judge" and not raw_options:
        return [
            {"key": "A", "content": "正确"},
            {"key": "B", "content": "错误"},
        ]
    if not isinstance(raw_options, list) or len(raw_options) < 2:
        raise BizError("选择题至少需要 2 个选项")
    options: list[dict] = []
    for idx, opt in enumerate(raw_options):
        if isinstance(opt, dict):
            key = str(opt.get("key") or chr(65 + idx)).strip().upper()[:2]
            content = str(opt.get("content") or "").strip()
        else:
            key = chr(65 + idx)
            content = str(opt).strip()
        if not content:
            raise BizError("选项内容不能为空")
        options.append({"key": key, "content": content})
    return options


def _opt_int(value) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
