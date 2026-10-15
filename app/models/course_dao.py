"""专业课程 DAO。"""
from __future__ import annotations

from ..db import execute, query_all, query_one


class CourseDao:
    def list_all(self) -> list[dict]:
        return query_all(
            "SELECT id, name, major, remark, created_at, updated_at "
            "FROM courses ORDER BY id DESC"
        )

    def get(self, course_id: int) -> dict | None:
        return query_one(
            "SELECT id, name, major, remark, created_at, updated_at "
            "FROM courses WHERE id = %s",
            (course_id,),
        )

    def get_by_name(self, name: str, exclude_id: int | None = None) -> dict | None:
        if exclude_id is None:
            return query_one("SELECT id FROM courses WHERE name = %s", (name,))
        return query_one(
            "SELECT id FROM courses WHERE name = %s AND id <> %s",
            (name, exclude_id),
        )

    def count_all(self) -> int:
        return query_one("SELECT COUNT(*) AS cnt FROM courses")["cnt"]

    def count_assignments(self, course_id: int) -> int:
        return query_one(
            "SELECT COUNT(*) AS cnt FROM assignments "
            "WHERE course_id = %s AND is_deleted = 0",
            (course_id,),
        )["cnt"]

    def insert(self, name: str, major: str, remark: str) -> int:
        return execute(
            "INSERT INTO courses (name, major, remark) VALUES (%s, %s, %s)",
            (name, major, remark),
            commit=True,
        ).lastrowid

    def update(self, course_id: int, name: str, major: str, remark: str) -> int:
        return execute(
            "UPDATE courses SET name = %s, major = %s, remark = %s WHERE id = %s",
            (name, major, remark, course_id),
            commit=True,
        ).rowcount

    def delete(self, course_id: int) -> int:
        return execute(
            "DELETE FROM courses WHERE id = %s", (course_id,), commit=True
        ).rowcount
