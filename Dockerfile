# AI 智能助手应用镜像
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 先装依赖（利用构建缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app ./app
COPY static ./static
COPY sql ./sql
COPY gunicorn.conf.py wsgi.py ./

EXPOSE 8000

# gthread worker 支持 SSE 长连接（见 gunicorn.conf.py）
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
