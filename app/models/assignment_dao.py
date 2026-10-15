"""作业 DAO。"""
from __future__ import annotations

from ..db import db_cursor, execute, query_all, query_one


class AssignmentDao:
    # ---------- 查询 ----------
    def list_page(self, class_id: int | None = None, course_id: int | None = None,
                  keyword: str | None = None, limit: int = 200) -> list[dict]:
        sql = (
            "SELECT a.id, a.title, a.class_id, a.course_id, a.difficulty, "
            "a.requirement, a.source, a.status, a.created_at, a.updated_at, "
            "c.name AS class_name, co.name AS course_name, "
            "(SELECT COUNT(*) FROM questions q WHERE q.assignment_id = a.id) AS question_count, "
            "(SELECT COUNT(*) FROM submissions s WHERE s.assignment_id = a.id) AS submission_count, "
            "(SELECT COUNT(*) FROM submissions s WHERE s.assignment_id = a.id AND s.status = 'pending') AS pending_count "
            "FROM assignments a "
            "LEFT JOIN classes c ON c.id = a.class_id "
            "LEFT JOIN courses co ON co.id = a.course_id "
            "WHERE a.is_deleted = 0"
        )
        params: list = []
        if class_id:
            sql += " AND a.class_id = %s"
            params.append(class_id)
        if course_id:
            sql += " AND a.course_id = %s"
            params.append(course_id)
        if keyword:
            sql += " AND a.title LIKE %s"
            params.append(f"%{keyword}%")
        sql += " ORDER BY a.updated_at DESC, a.id DESC LIMIT %s"
        params.append(limit)
        return query_all(sql, params)

    def list_recent(self, limit: int = 5) -> list[dict]:
        return query_all(
            "SELECT a.id, a.title, a.source, a.created_at, "
            "c.name AS class_name, co.name AS course_name, "
            "(SELECT COUNT(*) FROM questions q WHERE q.assignment_id = a.id) AS question_count "
            "FROM assignments a "
            "LEFT JOIN classes c ON c.id = a.class_id "
            "LEFT JOIN courses co ON co.id = a.course_id "
            "WHERE a.is_deleted = 0 ORDER BY a.updated_at DESC LIMIT %s",
            (limit,),
        )

    def get(self, assignment_id: int) -> dict | None:
        return query_one(
            "SELECT a.id, a.title, a.class_id, a.course_id, a.difficulty, "
            "a.requirement, a.source, a.status, a.created_at, a.updated_at, "
            "c.name AS class_name, co.name AS course_name, co.major AS course_major "
            "FROM assignments a "
            "LEFT JOIN classes c ON c.id = a.class_id "
            "LEFT JOIN courses co ON co.id = a.course_id "
            "WHERE a.id = %s AND a.is_deleted = 0",
            (assignment_id,),
        )

    def count_all(self) -> int:
        return query_one(
            "SELECT COUNT(*) AS cnt FROM assignments WHERE is_deleted = 0"
        )["cnt"]

    # ---------- 写入（cur 可选：传入时由外层统一事务提交） ----------
    def insert(self, title: str, class_id: int, course_id: int, difficulty: int,
               requirement: str, source: str = "manual", cur=None) -> int:
        sql = (
            "INSERT INTO assignments "
            "(title, class_id, course_id, difficulty, requirement, source) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        params = (title, class_id, course_id, difficulty, requirement, source)
        if cur is not None:
            cur.execute(sql, params)
            return cur.lastrowid
        return execute(sql, params, commit=True).lastrowid

    def update(self, assignment_id: int, title: str, class_id: int, course_id: int,
               difficulty: int, requirement: str) -> int:
        return execute(
            "UPDATE assignments SET title = %s, class_id = %s, course_id = %s, "
            "difficulty = %s, requirement = %s WHERE id = %s AND is_deleted = 0",
            (title, class_id, course_id, difficulty, requirement, assignment_id),
            commit=True,
        ).rowcount

    def soft_delete(self, assignment_id: int) -> int:
        with db_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE assignments SET is_deleted = 1 WHERE id = %s",
                (assignment_id,),
            )
            affected = cur.rowcount
            cur.execute(
                "DELETE FROM questions WHERE assignment_id = %s",
                (assignment_id,),
            )
            return affected
