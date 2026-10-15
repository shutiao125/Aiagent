"""LLM 客户端统一抽象。"""
from __future__ import annotations

from typing import Iterator


class LLMConfigError(Exception):
    """模型未配置或鉴权失败。"""


class LLMClient:
    """所有模型客户端遵循同一接口。

    chat(messages, stream=False, deep_thinking=False)
      - 普通模式：返回完整字符串
      - 流式模式：返回字典块迭代器，每块形如
        {"type": "content", "delta": "正式回复文本片段"} 或
        {"type": "reasoning", "delta": "模型深度思考片段（不落库、不参与回复拼接）"}
      - deep_thinking=True 时开启模型深度思考（可能产出 reasoning 块）；False 时直答
    """

    def chat(self, messages: list[dict], stream: bool = False,
             deep_thinking: bool = False):
        raise NotImplementedError
