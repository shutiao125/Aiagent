"""火山方舟 Doubao-Seed-2.1-pro 客户端（OpenAI 兼容协议）。"""
from __future__ import annotations

import logging
from typing import Iterator

from .base import LLMClient, LLMConfigError

logger = logging.getLogger(__name__)


class DoubaoClient(LLMClient):
    def __init__(self, config):
        if not getattr(config, "ARK_API_KEY", ""):
            raise LLMConfigError(
                "未配置火山方舟 ARK_API_KEY，请在 .env 中填写后重启；"
                "或设置 MOCK_LLM=1 使用离线模拟模式"
            )
        # 延迟导入：MOCK 模式/未安装 SDK 时不影响应用启动
        from openai import OpenAI

        self.model = config.ARK_MODEL
        self._client = OpenAI(
            api_key=config.ARK_API_KEY,
            base_url=config.ARK_BASE_URL,
            timeout=60,
        )
        logger.info("Doubao 客户端已初始化，模型/接入点：%s", self.model)

    def chat(self, messages: list[dict], stream: bool = False,
             deep_thinking: bool = False):
        if stream:
            return self._chat_stream(messages, deep_thinking)
        response = self._client.chat.completions.create(
            model=self.model, messages=messages, stream=False,
            extra_body={"thinking": {"type": "enabled" if deep_thinking else "disabled"}},
        )
        return response.choices[0].message.content or ""

    def _chat_stream(self, messages: list[dict], deep_thinking: bool) -> Iterator[dict]:
        response = self._client.chat.completions.create(
            model=self.model, messages=messages, stream=True,
            extra_body={"thinking": {"type": "enabled" if deep_thinking else "disabled"}},
        )
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta:
                continue
            # 深度思考模型先产出 reasoning_content（思考过程），再产出 content（正式回复）
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield {"type": "reasoning", "delta": reasoning}
            if delta.content:
                yield {"type": "content", "delta": delta.content}
