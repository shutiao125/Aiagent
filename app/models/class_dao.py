"""班级 DAO。"""
from __future__ import annotations

from ..db import execute, query_all, query_one


class ClassDao:
    def list_all(self) -> list[dict]:
        return query_all(
            "SELECT id, name, grade, remark, created_at, updated_at "
            "FROM classes ORDER BY id DESC"
        )

    def get(self, class_id: int) -> dict | None:
        return query_one(
            "SELECT id, name, grade, remark, created_at, updated_at "
            "FROM classes WHERE id = %s",
            (class_id,),
        )

    def get_by_name(self, name: str, exclude_id: int | None = None) -> dict | None:
        if exclude_id is None:
            return query_one("SELECT id FROM classes WHERE name = %s", (name,))
        return query_one(
            "SELECT id FROM classes WHERE name = %s AND id <> %s",
            (name, exclude_id),
        )

    def count_all(self) -> int:
        return query_one("SELECT COUNT(*) AS cnt FROM classes")["cnt"]

    def count_assignments(self, class_id: int) -> int:
        return query_one(
            "SELECT COUNT(*) AS cnt FROM assignments "
            "WHERE class_id = %s AND is_deleted = 0",
            (class_id,),
        )["cnt"]

    def insert(self, name: str, grade: str, remark: str) -> int:
        return execute(
            "INSERT INTO classes (name, grade, remark) VALUES (%s, %s, %s)",
            (name, grade, remark),
            commit=True,
        ).lastrowid

    def update(self, class_id: int, name: str, grade: str, remark: str) -> int:
        return execute(
            "UPDATE classes SET name = %s, grade = %s, remark = %s WHERE id = %s",
            (name, grade, remark, class_id),
            commit=True,
        ).rowcount

    def delete(self, class_id: int) -> int:
        return execute(
            "DELETE FROM classes WHERE id = %s", (class_id,), commit=True
        ).rowcount
