"""MySQL 连接池（PyMySQL + DBUtils PooledDB）。"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterable, Optional

import pymysql
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)

_pool: Optional[PooledDB] = None


def init_pool(config) -> PooledDB:
    """根据应用配置初始化全局连接池。"""
    global _pool
    _pool = PooledDB(
        creator=pymysql,
        mincached=1,
        maxcached=getattr(config, "DB_POOL_SIZE", 5),
        maxconnections=getattr(config, "DB_POOL_SIZE", 5) * 4,
        blocking=True,
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset=getattr(config, "DB_CHARSET", "utf8mb4"),
        autocommit=False,
        cursorclass=DictCursor,
    )
    return _pool


@contextmanager
def db_cursor(commit: bool = False):
    """获取游标的上下文管理器，自动提交/回滚/归还连接。"""
    if _pool is None:
        raise RuntimeError("数据库连接池尚未初始化")
    conn = _pool.connection()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def execute(sql: str, params: Iterable[Any] | dict | None = None, commit: bool = False):
    """执行写操作，返回 lastrowid / rowcount 元信息游标。"""
    with db_cursor(commit=commit) as cur:
        cur.execute(sql, params)
        return cur


def query_all(sql: str, params: Iterable[Any] | dict | None = None) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def query_one(sql: str, params: Iterable[Any] | dict | None = None) -> Optional[dict]:
    with db_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()
