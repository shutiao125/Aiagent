"""学生作业提交 / 作答明细 DAO。"""
from __future__ import annotations

from ..db import query_all, query_one


class SubmissionDao:
    # ---------- 提交 ----------
    def insert(self, assignment_id: int, student_name: str, student_no: str,
               max_score: int, cur=None) -> int:
        sql = (
            "INSERT INTO submissions "
            "(assignment_id, student_name, student_no, max_score) "
            "VALUES (%s, %s, %s, %s)"
        )
        params = (assignment_id, student_name, student_no, max_score)
        if cur is not None:
            cur.execute(sql, params)
            return cur.lastrowid
        from ..db import execute
        return execute(sql, params, commit=True).lastrowid

    def exists_student(self, assignment_id: int, student_no: str,
                       exclude_id: int | None = None) -> bool:
        if exclude_id is None:
            row = query_one(
                "SELECT id FROM submissions WHERE assignment_id = %s AND student_no = %s",
                (assignment_id, student_no),
            )
        else:
            row = query_one(
                "SELECT id FROM submissions "
                "WHERE assignment_id = %s AND student_no = %s AND id <> %s",
                (assignment_id, student_no, exclude_id),
            )
        return row is not None

    def get(self, submission_id: int) -> dict | None:
        return query_one(
            "SELECT * FROM submissions WHERE id = %s", (submission_id,)
        )

    def get_with_assignment(self, submission_id: int) -> dict | None:
        return query_one(
            "SELECT s.*, a.title AS assignment_title, a.class_id, a.course_id, "
            "c.name AS class_name, co.name AS course_name "
            "FROM submissions s "
            "INNER JOIN assignments a ON a.id = s.assignment_id AND a.is_deleted = 0 "
            "LEFT JOIN classes c ON c.id = a.class_id "
            "LEFT JOIN courses co ON co.id = a.course_id "
            "WHERE s.id = %s",
            (submission_id,),
        )

    def list_(self, status: str | None = None, class_id: int | None = None,
              assignment_id: int | None = None, keyword: str | None = None,
              limit: int = 300) -> list[dict]:
        sql = (
            "SELECT s.id, s.assignment_id, s.student_name, s.student_no, s.status, "
            "s.total_score, s.max_score, s.submitted_at, s.graded_at, "
            "a.title AS assignment_title, c.name AS class_name, co.name AS course_name, "
            "(SELECT COUNT(*) FROM submission_answers sa WHERE sa.submission_id = s.id) AS answer_count, "
            "(SELECT COUNT(*) FROM submission_answers sa WHERE sa.submission_id = s.id AND sa.is_correct IS NULL) AS pending_count, "
            "(SELECT COUNT(*) FROM submission_answers sa WHERE sa.submission_id = s.id AND sa.is_correct = 1) AS correct_count "
            "FROM submissions s "
            "INNER JOIN assignments a ON a.id = s.assignment_id AND a.is_deleted = 0 "
            "LEFT JOIN classes c ON c.id = a.class_id "
            "LEFT JOIN courses co ON co.id = a.course_id "
            "WHERE 1=1"
        )
        params: list = []
        if status in ("pending", "graded"):
            sql += " AND s.status = %s"
            params.append(status)
        if class_id:
            sql += " AND a.class_id = %s"
            params.append(class_id)
        if assignment_id:
            sql += " AND s.assignment_id = %s"
            params.append(assignment_id)
        if keyword:
            sql += " AND (s.student_name LIKE %s OR s.student_no LIKE %s OR a.title LIKE %s)"
            like = f"%{keyword}%"
            params.extend([like, like, like])
        sql += " ORDER BY s.submitted_at DESC, s.id DESC LIMIT %s"
        params.append(limit)
        return query_all(sql, params)

    def count_pending(self) -> int:
        return query_one(
            "SELECT COUNT(*) AS cnt FROM submissions WHERE status = 'pending'"
        )["cnt"]

    def finalize(self, submission_id: int, status: str, total_score: int, cur=None) -> None:
        sql = (
            "UPDATE submissions SET status = %s, total_score = %s, "
            "graded_at = IF(%s = 'graded', NOW(), graded_at) WHERE id = %s"
        )
        params = (status, total_score, status, submission_id)
        if cur is not None:
            cur.execute(sql, params)
            return
        from ..db import execute
        execute(sql, params, commit=True)

    # ---------- 作答明细 ----------
    def insert_answer(self, submission_id: int, question_id: int, seq: int,
                      qtype: str, response: str, cur=None) -> int:
        sql = (
            "INSERT INTO submission_answers "
            "(submission_id, question_id, seq, type, response) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        params = (submission_id, question_id, seq, qtype, response)
        if cur is not None:
            cur.execute(sql, params)
            return cur.lastrowid
        from ..db import execute
        return execute(sql, params, commit=True).lastrowid

    def list_answers_with_questions(self, submission_id: int) -> list[dict]:
        """学生作答 JOIN 题目（题干/选项/参考答案/分值）。"""
        return query_all(
            "SELECT sa.id AS answer_id, sa.submission_id, sa.question_id, sa.seq, "
            "sa.type, sa.response, sa.is_correct, sa.score AS got_score, sa.grader, "
            "sa.comment, sa.graded_at, "
            "q.stem, q.options_json, q.answer AS reference_answer, "
            "q.analysis AS reference_analysis, q.score AS max_score "
            "FROM submission_answers sa "
            "INNER JOIN questions q ON q.id = sa.question_id "
            "WHERE sa.submission_id = %s ORDER BY sa.seq, sa.id",
            (submission_id,),
        )

    def update_grade(self, answer_id: int, is_correct: int, score: int,
                     comment: str, cur=None) -> None:
        sql = (
            "UPDATE submission_answers SET is_correct = %s, score = %s, "
            "comment = %s, grader = 'teacher', graded_at = NOW() WHERE id = %s"
        )
        params = (is_correct, score, comment, answer_id)
        if cur is not None:
            cur.execute(sql, params)
            return
        from ..db import execute
        execute(sql, params, commit=True)

    def apply_ai_grade(self, answer_id: int, is_correct: int | None, score: int | None,
                       comment: str, cur=None) -> None:
        """AI 自动批改落库；is_correct 为 None 表示降级人工批。"""
        if is_correct is None:
            sql = (
                "UPDATE submission_answers SET is_correct = NULL, score = NULL, "
                "grader = '', comment = %s, graded_at = NULL WHERE id = %s"
            )
            params = (comment, answer_id)
        else:
            sql = (
                "UPDATE submission_answers SET is_correct = %s, score = %s, "
                "grader = 'ai', comment = %s, graded_at = NOW() WHERE id = %s"
            )
            params = (is_correct, score, comment, answer_id)
        if cur is not None:
            cur.execute(sql, params)
            return
        from ..db import execute
        execute(sql, params, commit=True)

    def score_summary(self, submission_id: int, cur=None) -> dict:
        sql = (
            "SELECT COUNT(*) AS total_cnt, "
            "SUM(is_correct IS NULL) AS pending_cnt, "
            "COALESCE(SUM(CASE WHEN is_correct IS NOT NULL THEN score ELSE 0 END), 0) AS scored_sum "
            "FROM submission_answers WHERE submission_id = %s"
        )
        if cur is not None:
            cur.execute(sql, (submission_id,))
            return cur.fetchone()
        return query_one(sql, (submission_id,))
