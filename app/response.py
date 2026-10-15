"""统一响应结构与业务异常。

所有 REST 接口统一返回：{"code": int, "message": str, "data": any}
"""
from __future__ import annotations

from typing import Any

from flask import jsonify


class ErrorCode:
    OK = 0
    BIZ_ERROR = 4000          # 通用业务/参数错误
    NOT_FOUND = 4004
    LLM_CONFIG = 4010        # 模型未配置/鉴权失败
    LLM_ERROR = 4011         # 模型调用异常
    INTERNAL_ERROR = 5000


class BizError(Exception):
    """业务异常：路由/服务层抛出后由全局处理器转成统一 JSON。"""

    def __init__(
        self,
        message: str,
        code: int = ErrorCode.BIZ_ERROR,
        http_status: int = 400,
        data: Any = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.data = data


def ok(data: Any = None, message: str = "ok"):
    return jsonify({"code": ErrorCode.OK, "message": message, "data": data})


def fail(message: str, code: int = ErrorCode.BIZ_ERROR, http_status: int = 400, data: Any = None):
    response = jsonify({"code": code, "message": message, "data": data})
    response.status_code = http_status
    return response
