"""消息历史业务服务。"""
from __future__ import annotations

from ..models.conversation_dao import ConversationDao
from ..models.message_dao import MessageDao
from ..utils.serialization import to_jsonable


class MessageService:
    def __init__(self):
        self.message_dao = MessageDao()
        self.conversation_dao = ConversationDao()

    @staticmethod
    def _serialize(row: dict) -> dict:
        return to_jsonable(row)

    def history(self, conversation_id: int) -> list[dict]:
        # 会话不存在或已删除时不返回任何消息
        if self.conversation_dao.get_active(conversation_id) is None:
            from ..response import BizError, ErrorCode
            raise BizError("会话不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
        rows = self.message_dao.list_by_conversation(conversation_id)
        return [self._serialize(r) for r in rows]
