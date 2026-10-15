"""对话编排服务：消息落库 → 上下文拼接 → 调用 LLM（流式/普通）。"""
from __future__ import annotations

import logging
from typing import Iterator

from ..config import Config
from ..llm import get_llm_client
from ..llm.base import LLMConfigError
from ..models.conversation_dao import ConversationDao
from ..models.message_dao import MessageDao
from ..response import BizError, ErrorCode
from ..utils.sse import format_sse

logger = logging.getLogger(__name__)


class CompletionService:
    def __init__(self, config=Config):
        self.config = config
        self.conversation_dao = ConversationDao()
        self.message_dao = MessageDao()

    # ---------- 普通（非流式）模式 ----------
    def reply_once(self, conversation_id: int, text: str,
                   deep_thinking: bool = False) -> dict:
        conv = self.conversation_dao.get_active(conversation_id)
        if conv is None:
            self._raise_not_found()
        _user_id, first_turn = self._store_user_message(conversation_id, text)

        messages = self._build_context_messages(conversation_id)
        client = get_llm_client(self.config)
        try:
            answer = client.chat(messages, stream=False, deep_thinking=deep_thinking)
        except LLMConfigError as exc:
            raise BizError(str(exc), code=ErrorCode.LLM_CONFIG, http_status=503) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Doubao 普通调用失败")
            raise BizError(
                f"模型调用失败：{exc}", code=ErrorCode.LLM_ERROR, http_status=502
            ) from exc

        self.message_dao.insert(conversation_id, "assistant", answer)
        if first_turn and self._has_default_title(conv):
            self.conversation_dao.rename(conversation_id, text[: self.config.TITLE_MAX_LEN])
        self.conversation_dao.touch(conversation_id, answer)
        return {
            "status": "ok",
            "conversation_id": conversation_id,
            "content": answer,
        }

    # ---------- 流式（SSE）模式 ----------
    def stream_reply(self, conversation_id: int, text: str,
                     deep_thinking: bool = False) -> Iterator[str]:
        yield format_sse("meta", {"conversation_id": conversation_id})

        conv = self.conversation_dao.get_active(conversation_id)
        if conv is None:
            yield format_sse(
                "error",
                {"code": ErrorCode.NOT_FOUND, "message": "会话不存在或已删除"},
            )
            yield format_sse("done", {"status": "not_found"})
            return

        _user_id, first_turn = self._store_user_message(conversation_id, text)

        messages = self._build_context_messages(conversation_id)
        logger.info(
            "调用模型 conversation_id=%s deep_thinking=%s，提交消息结构：%s",
            conversation_id, deep_thinking,
            [{"role": m["role"], "len": len(m["content"])} for m in messages],
        )

        collected: list[str] = []
        reasoning_len = 0
        try:
            # 客户端初始化（可能抛 LLMConfigError）必须在 try 内，
            # 否则 SSE 头已发出后只能断流，无法下发结构化 error 事件。
            client = get_llm_client(self.config)
            for block in client.chat(messages, stream=True,
                                     deep_thinking=deep_thinking):
                piece = block.get("delta", "")
                if block.get("type") == "reasoning":
                    # 思考过程仅实时透传给前端展示，不拼接、不落库
                    reasoning_len += len(piece)
                    yield format_sse("thinking", {"content": piece})
                    continue
                collected.append(piece)
                yield format_sse("delta", {"content": piece})
        except LLMConfigError as exc:
            self._save_partial(conversation_id, collected)
            yield format_sse("error", {"code": ErrorCode.LLM_CONFIG, "message": str(exc)})
            yield format_sse("done", {"status": "error"})
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Doubao 流式调用中断")
            self._save_partial(conversation_id, collected)
            yield format_sse(
                "error",
                {
                    "code": ErrorCode.LLM_ERROR,
                    "message": f"模型回复中断，已保留已生成的 {sum(len(c) for c in collected)} 字片段：{exc}",
                },
            )
            yield format_sse("done", {"status": "error"})
            return

        answer = "".join(collected)
        if reasoning_len:
            logger.info("模型深度思考 %s 字，正式回复 %s 字", reasoning_len, len(answer))
        self.message_dao.insert(conversation_id, "assistant", answer)
        if first_turn and self._has_default_title(conv):
            self.conversation_dao.rename(
                conversation_id, text[: self.config.TITLE_MAX_LEN]
            )
        self.conversation_dao.touch(conversation_id, answer)
        yield format_sse("done", {"status": "ok"})

    # ---------- 内部步骤 ----------
    @staticmethod
    def _has_default_title(conv: dict) -> bool:
        """仅当标题仍是系统默认值时才允许首条消息自动命名，避免覆盖用户手动改名。"""
        return (conv or {}).get("title") in (None, "", "新会话")

    def _store_user_message(self, conversation_id: int, text: str) -> tuple[int, bool]:
        """用户消息一律正常落库；返回 (消息ID, 是否首轮)。"""
        first_turn = len(self.message_dao.recent_normal(conversation_id, 1)) == 0
        user_id = self.message_dao.insert(conversation_id, "user", text)
        self.conversation_dao.touch(conversation_id, text)
        return user_id, first_turn

    def _build_context_messages(self, conversation_id: int) -> list[dict]:
        """拼接 system + 最近 N 条历史（含本轮 user），保持角色顺序。"""
        rows = self.message_dao.recent_normal(
            conversation_id, self.config.CONTEXT_LIMIT
        )
        messages = [{"role": "system", "content": self.config.SYSTEM_PROMPT}]
        messages.extend({"role": row["role"], "content": row["content"]} for row in rows)
        return messages

    def _save_partial(self, conversation_id: int, collected: list[str]) -> None:
        partial = "".join(collected)
        if partial:
            self.message_dao.insert(conversation_id, "assistant", partial)
            self.conversation_dao.touch(conversation_id, partial)

    @staticmethod
    def _raise_not_found():
        raise BizError("会话不存在或已删除", code=ErrorCode.NOT_FOUND, http_status=404)
