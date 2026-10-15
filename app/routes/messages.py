"""消息路由：历史回溯、普通发送、SSE 流式发送。"""
from __future__ import annotations

from flask import Blueprint, Response, request

from ..response import ok
from ..services import Services
from ..utils.validation import require_text

bp = Blueprint("messages", __name__, url_prefix="/api/conversations")


@bp.get("/<int:conversation_id>/messages")
def list_messages(conversation_id: int):
    return ok(Services.messages.history(conversation_id))


@bp.post("/<int:conversation_id>/messages")
def send_message_once(conversation_id: int):
    """普通（非流式）发送。"""
    payload = request.get_json(silent=True) or {}
    text = require_text(payload.get("content"))
    deep_thinking = payload.get("deep_thinking") is True
    return ok(Services.completions.reply_once(conversation_id, text, deep_thinking))


@bp.post("/<int:conversation_id>/messages/stream")
def send_message_stream(conversation_id: int):
    """SSE 流式发送。"""
    payload = request.get_json(silent=True) or {}
    text = require_text(payload.get("content"))
    deep_thinking = payload.get("deep_thinking") is True
    return Response(
        Services.completions.stream_reply(conversation_id, text, deep_thinking),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
