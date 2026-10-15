"""会话生命周期路由。"""
from __future__ import annotations

from flask import Blueprint, request

from ..response import ok
from ..services import Services

bp = Blueprint("conversations", __name__, url_prefix="/api/conversations")


@bp.get("")
def list_conversations():
    return ok(Services.chats.list_chats())


@bp.post("")
def create_conversation():
    payload = request.get_json(silent=True) or {}
    return ok(Services.chats.create_chat(payload.get("title")))


@bp.get("/<int:conversation_id>")
def get_conversation(conversation_id: int):
    return ok(Services.chats.get_chat(conversation_id))


@bp.patch("/<int:conversation_id>")
def rename_conversation(conversation_id: int):
    payload = request.get_json(silent=True) or {}
    return ok(Services.chats.rename_chat(conversation_id, payload.get("title", "")))


@bp.patch("/<int:conversation_id>/pin")
def pin_conversation(conversation_id: int):
    payload = request.get_json(silent=True) or {}
    return ok(Services.chats.pin_chat(conversation_id, bool(payload.get("pinned"))))


@bp.delete("/<int:conversation_id>")
def delete_conversation(conversation_id: int):
    Services.chats.delete_chat(conversation_id)
    return ok(None, message="删除成功")
