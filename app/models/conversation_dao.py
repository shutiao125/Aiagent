"""会话 DAO。"""
from __future__ import annotations

from ..db import db_cursor, execute, query_all, query_one

_BASE_COLUMNS = (
    "id, title, pinned, is_deleted, last_preview, created_at, updated_at"
)


class ConversationDao:
    def list_active(self) -> list[dict]:
        # 置顶优先，同组内最近更新优先
        return query_all(
            f"SELECT {_BASE_COLUMNS} FROM conversations "
            "WHERE is_deleted = 0 ORDER BY pinned DESC, updated_at DESC, id DESC"
        )

    def get(self, conversation_id: int) -> dict | None:
        return query_one(
            f"SELECT {_BASE_COLUMNS} FROM conversations WHERE id = %s",
            (conversation_id,),
        )

    def get_active(self, conversation_id: int) -> dict | None:
        return query_one(
            f"SELECT {_BASE_COLUMNS} FROM conversations "
            "WHERE id = %s AND is_deleted = 0",
            (conversation_id,),
        )

    def insert(self, title: str) -> int:
        cursor = execute(
            "INSERT INTO conversations (title) VALUES (%s)", (title,), commit=True
        )
        return cursor.lastrowid

    def rename(self, conversation_id: int, title: str) -> int:
        cursor = execute(
            "UPDATE conversations SET title = %s WHERE id = %s AND is_deleted = 0",
            (title, conversation_id),
            commit=True,
        )
        return cursor.rowcount

    def set_pinned(self, conversation_id: int, pinned: bool) -> int:
        cursor = execute(
            "UPDATE conversations SET pinned = %s WHERE id = %s AND is_deleted = 0",
            (1 if pinned else 0, conversation_id),
            commit=True,
        )
        return cursor.rowcount

    def touch(self, conversation_id: int, preview: str) -> None:
        """刷新最近消息摘要与更新时间。"""
        execute(
            "UPDATE conversations SET last_preview = %s, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = %s",
            (preview[:200], conversation_id),
            commit=True,
        )

    def soft_delete(self, conversation_id: int) -> int:
        """逻辑删除会话，同时逻辑删除其全部消息（单事务，同生共死）。"""
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE messages SET is_deleted = 1 WHERE conversation_id = %s",
                (conversation_id,),
            )
            cursor.execute(
                "UPDATE conversations SET is_deleted = 1 WHERE id = %s",
                (conversation_id,),
            )
            return cursor.rowcount
