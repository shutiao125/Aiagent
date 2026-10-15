"""健康检查路由。"""
from __future__ import annotations

from flask import Blueprint

from ..config import Config
from ..db import query_one
from ..response import ok

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    db_ok = False
    try:
        query_one("SELECT 1 AS v")
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return ok({
        "status": "up" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "llm_mode": "mock" if Config.MOCK_LLM else "doubao",
        "model": Config.ARK_MODEL,
    })
