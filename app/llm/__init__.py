"""大模型接入层：对外暴露统一的 get_llm_client()。"""
from .base import LLMClient, LLMConfigError

_client = None


def get_llm_client(config):
    """按配置返回 Doubao 真实客户端或 MOCK 客户端（单例）。"""
    global _client
    if _client is not None:
        return _client
    if getattr(config, "MOCK_LLM", False):
        from .mock_client import MockLLMClient
        _client = MockLLMClient()
    else:
        from .doubao import DoubaoClient
        _client = DoubaoClient(config)
    return _client


__all__ = ["get_llm_client", "LLMClient", "LLMConfigError"]
