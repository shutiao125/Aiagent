"""集中式配置：所有运行参数均来自环境变量（本地开发可由 .env 注入）。"""
import os

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # MySQL
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "ai_assistant")
    DB_CHARSET = "utf8mb4"
    DB_CONNECT_RETRIES = int(os.getenv("DB_CONNECT_RETRIES", "30"))
    DB_CONNECT_WAIT = float(os.getenv("DB_CONNECT_WAIT", "2"))
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))

    # 火山方舟 Doubao
    ARK_API_KEY = os.getenv("ARK_API_KEY", "").strip()
    ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").strip()
    ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-2-1-pro").strip()

    # 对话
    CONTEXT_LIMIT = int(os.getenv("CONTEXT_LIMIT", "20"))
    SYSTEM_PROMPT = os.getenv(
        "SYSTEM_PROMPT",
        "你是 AI 辅助教学系统中的答疑助教，面向高校师生，用严谨、清晰、鼓励式的"
        "中文回答学习问题，讲解知识点、给出思路与示例，不直接替学生完成可提交的作业。",
    ).strip()
    MOCK_LLM = _as_bool(os.getenv("MOCK_LLM"), default=True)

    # 会话标题取首条消息的最大长度
    TITLE_MAX_LEN = 20
