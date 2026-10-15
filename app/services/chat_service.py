"""会话生命周期业务服务。"""
from __future__ import annotations

from ..models.conversation_dao import ConversationDao
from ..response import BizError, ErrorCode
from ..utils.serialization import to_jsonable


class ChatService:
    def __init__(self):
        self.dao = ConversationDao()

    @staticmethod
    def _serialize(row: dict) -> dict:
        row = to_jsonable(row)
        row["pinned"] = bool(row.get("pinned"))
        row["is_deleted"] = bool(row.get("is_deleted"))
        return row

    def list_chats(self) -> list[dict]:
        return [self._serialize(r) for r in self.dao.list_active()]

    def create_chat(self, title: str | None = None) -> dict:
        clean_title = self._clean_title(title) if title is not None else "新会话"
        conversation_id = self.dao.insert(clean_title)
        return self._serialize(self.dao.get(conversation_id))

    def get_chat(self, conversation_id: int) -> dict:
        return self._serialize(self.require_active(conversation_id))

    def rename_chat(self, conversation_id: int, title: str) -> dict:
        clean_title = self._clean_title(title)
        if self.dao.rename(conversation_id, clean_title) == 0:
            raise BizError("会话不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        return self.get_chat(conversation_id)

    def pin_chat(self, conversation_id: int, pinned: bool) -> dict:
        if self.dao.set_pinned(conversation_id, pinned) == 0:
            raise BizError("会话不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        return self.get_chat(conversation_id)

    def delete_chat(self, conversation_id: int) -> None:
        if self.dao.soft_delete(conversation_id) == 0:
            raise BizError("会话不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)

    def require_active(self, conversation_id: int) -> dict:
        row = self.dao.get_active(conversation_id)
        if row is None:
            raise BizError("会话不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        return row

    @staticmethod
    def _clean_title(title) -> str:
        if not isinstance(title, str):
            raise BizError("会话标题必须为字符串")
        title = title.strip()
        if not title:
            raise BizError("会话标题不能为空")
        return title[:100]
