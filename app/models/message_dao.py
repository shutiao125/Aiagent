"""消息 DAO。"""
from __future__ import annotations

from ..db import execute, query_all

_BASE_COLUMNS = (
    "m.id, m.conversation_id AS conversation_id, m.role, m.content, "
    "m.status, m.blocked_rule AS blocked_rule, m.created_at"
)


class MessageDao:
    def insert(
        self,
        conversation_id: int,
        role: str,
        content: str,
        status: str = "normal",
        blocked_rule: str = "",
    ) -> int:
        cursor = execute(
            "INSERT INTO messages (conversation_id, role, content, status, blocked_rule) "
            "VALUES (%s, %s, %s, %s, %s)",
            (conversation_id, role, content, status, blocked_rule),
            commit=True,
        )
        return cursor.lastrowid

    def list_by_conversation(self, conversation_id: int) -> list[dict]:
        """完整历史，按时间（id）正序；会话被删则查不到任何消息。"""
        return query_all(
            f"SELECT {_BASE_COLUMNS} FROM messages m "
            "INNER JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.conversation_id = %s AND m.is_deleted = 0 AND c.is_deleted = 0 "
            "ORDER BY m.id ASC",
            (conversation_id,),
        )

    def recent_normal(self, conversation_id: int, limit: int) -> list[dict]:
        """最近若干条正常消息（用于模型上下文），返回时已反转为时间正序。"""
        rows = query_all(
            "SELECT id, role, content FROM messages "
            "WHERE conversation_id = %s AND is_deleted = 0 AND status = 'normal' "
            "AND role IN ('user', 'assistant') "
            "ORDER BY id DESC LIMIT %s",
            (conversation_id, limit),
        )
        rows.reverse()
        return rows
