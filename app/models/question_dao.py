"""习题 DAO。"""
from __future__ import annotations

import json
from typing import Any

from ..db import execute, query_all, query_one


def _dump_options(options: Any) -> str | None:
    if not options:
        return None
    return json.dumps(options, ensure_ascii=False)


class QuestionDao:
    def list_by_assignment(self, assignment_id: int) -> list[dict]:
        return query_all(
            "SELECT id, assignment_id, seq, type, stem, options_json, answer, "
            "analysis, score, created_at, updated_at "
            "FROM questions WHERE assignment_id = %s ORDER BY seq, id",
            (assignment_id,),
        )

    def get(self, question_id: int) -> dict | None:
        return query_one(
            "SELECT id, assignment_id, seq, type, stem, options_json, answer, "
            "analysis, score FROM questions WHERE id = %s",
            (question_id,),
        )

    def max_seq(self, assignment_id: int, cur=None) -> int:
        sql = "SELECT COALESCE(MAX(seq), 0) AS m FROM questions WHERE assignment_id = %s"
        if cur is not None:
            cur.execute(sql, (assignment_id,))
            return cur.fetchone()["m"]
        return query_one(sql, (assignment_id,))["m"]

    def count_all(self) -> int:
        return query_one("SELECT COUNT(*) AS cnt FROM questions")["cnt"]

    def insert(self, assignment_id: int, seq: int, qtype: str, stem: str,
               options: Any, answer: str, analysis: str, score: int = 5,
               cur=None) -> int:
        sql = (
            "INSERT INTO questions "
            "(assignment_id, seq, type, stem, options_json, answer, analysis, score) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        )
        params = (assignment_id, seq, qtype, stem, _dump_options(options),
                  answer, analysis, score)
        if cur is not None:
            cur.execute(sql, params)
            return cur.lastrowid
        return execute(sql, params, commit=True).lastrowid

    def batch_insert(self, assignment_id: int, questions: list[dict], cur=None) -> int:
        """questions: [{type, stem, options, answer, analysis, score?}]，seq 自动从 1 开始。"""
        own = cur is None
        if own:
            from ..db import db_cursor
            ctx = db_cursor(commit=True)
            cur = ctx.__enter__()
        try:
            for idx, q in enumerate(questions, start=1):
                self.insert(
                    assignment_id, q.get("seq") or idx, q["type"], q["stem"],
                    q.get("options"), q.get("answer", ""), q.get("analysis", ""),
                    int(q.get("score") or 5),
                    cur=cur,
                )
            return len(questions)
        finally:
            if own:
                ctx.__exit__(None, None, None)

    def update(self, question_id: int, qtype: str, stem: str, options: Any,
               answer: str, analysis: str, score: int = 5) -> int:
        return execute(
            "UPDATE questions SET type = %s, stem = %s, options_json = %s, "
            "answer = %s, analysis = %s, score = %s WHERE id = %s",
            (qtype, stem, _dump_options(options), answer, analysis, score, question_id),
            commit=True,
        ).rowcount

    def delete(self, question_id: int) -> int:
        return execute(
            "DELETE FROM questions WHERE id = %s", (question_id,), commit=True
        ).rowcount
