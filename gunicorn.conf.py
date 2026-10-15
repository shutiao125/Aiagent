"""gunicorn 配置：线程模式承载 SSE 长连接。"""
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "8"))
worker_class = "gthread"
timeout = 120
graceful_timeout = 10
loglevel = "info"
accesslog = "-"
errorlog = "-"
