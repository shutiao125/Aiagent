"""入参校验工具。"""
from __future__ import annotations

from ..response import BizError


def require_text(content) -> str:
    """提取并校验用户输入文本，非法输入抛 BizError。"""
    if not isinstance(content, str):
        raise BizError("消息内容必须为文本字符串")
    text = content.strip()
    if not text:
        raise BizError("消息内容不能为空")
    if len(text) > 8000:
        raise BizError("单条消息长度不能超过 8000 字")
    return text
