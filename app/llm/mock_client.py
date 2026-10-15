"""离线 MOCK 客户端：无需 API Key 即可模拟流式/普通回复，便于联调演示。"""
from __future__ import annotations

import time
from typing import Iterator


class MockLLMClient:
    def _build_reply(self, messages: list[dict]) -> str:
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break
        history_rounds = sum(1 for m in messages if m.get("role") == "user") - 1
        return (
            f"【MOCK 模拟回复】\n\n"
            f"我已收到你的问题：**{last_user[:60]}**\n\n"
            f"- 当前已携带历史对话轮数：{max(history_rounds, 0)} 轮\n"
            f"- 提交给模型的消息总数：{len(messages)} 条（含 system）\n\n"
            "这是一条本地模拟的流式回复，用于验证「多轮上下文拼接」与"
            "「逐字流式渲染」链路。配置真实的火山方舟 ARK_API_KEY 并将 "
            "MOCK_LLM 置为 0 后，将由 Doubao-Seed-2.1-pro 生成回复。"
        )

    def chat(self, messages: list[dict], stream: bool = False,
             deep_thinking: bool = False):
        # MOCK 模式不区分深度思考，deep_thinking 仅用于链路透传
        reply = self._build_reply(messages)
        if not stream:
            return reply
        return self._stream(reply)

    @staticmethod
    def _stream(text: str) -> Iterator[dict]:
        # 按 2~4 个字符切块，模拟真实打字节奏（MOCK 无思考阶段，全部为 content）
        buf = ""
        for ch in text:
            buf += ch
            if len(buf) >= 3 or ch in "\n。！？":
                yield {"type": "content", "delta": buf}
                buf = ""
                time.sleep(0.01)
        if buf:
            yield {"type": "content", "delta": buf}
