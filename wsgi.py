"""容器内 gunicorn 入口：gunicorn -c gunicorn.conf.py wsgi:app"""
from app import create_app

app = create_app()
