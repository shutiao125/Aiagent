"""启动引导：等待数据库就绪、幂等建库建表、写入内置示例班级与课程。"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import pymysql

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

# 内置示例班级（name, grade, remark）
SEED_CLASSES = [
    ("计科2301", "2023级", "计算机科学与技术专业 1 班"),
    ("软工2302", "2023级", "软件工程专业 2 班"),
]

# 内置示例专业课程（name, major, remark）
SEED_COURSES = [
    ("数据结构", "计算机科学与技术", "线性表、树、图、查找与排序"),
    ("高等数学", "理工科公共课", "微积分、级数与微分方程"),
    ("大学英语", "公共基础课", "读写译综合训练"),
]


def _server_connection(config):
    """连接 MySQL 服务（不指定数据库），用于建库。"""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset=config.DB_CHARSET,
        autocommit=True,
    )


def wait_for_database(config) -> None:
    """重试等待 MySQL 就绪，然后确保业务数据库存在。"""
    last_error = None
    for attempt in range(1, config.DB_CONNECT_RETRIES + 1):
        try:
            conn = _server_connection(config)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` "
                        f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
            finally:
                conn.close()
            logger.info("MySQL 已就绪，数据库 %s 已确认存在", config.DB_NAME)
            return
        except Exception as exc:  # noqa: BLE001 - 启动阶段需要吞掉异常做重试
            last_error = exc
            logger.warning(
                "等待 MySQL 就绪（第 %s/%s 次）：%s",
                attempt, config.DB_CONNECT_RETRIES, exc,
            )
            time.sleep(config.DB_CONNECT_WAIT)
    raise RuntimeError(f"无法连接 MySQL，已重试 {config.DB_CONNECT_RETRIES} 次：{last_error}")


def _load_ddl_statements() -> list[str]:
    """解析 schema.sql：去掉注释与 CREATE DATABASE / USE 语句，按分号拆为独立 DDL。"""
    clean_lines = [
        raw_line for raw_line in SCHEMA_FILE.read_text(encoding="utf-8").splitlines()
        if raw_line.strip() and not raw_line.strip().startswith("--")
    ]
    statements: list[str] = []
    for stmt in "\n".join(clean_lines).split(";"):
        cleaned = stmt.strip()
        if not cleaned:
            continue
        head = cleaned.upper()
        if head.startswith("CREATE DATABASE") or head.startswith("USE "):
            continue
        statements.append(cleaned)
    return statements


def _ensure_column(cur, table: str, column: str, ddl: str) -> None:
    """旧库幂等加列：直接执行 ALTER，重复列名(1060)视为已存在。

    本机 MySQL 8 的 information_schema 视图定义者损坏，
    SHOW COLUMNS / information_schema.COLUMNS 均无法查询，故不用元数据探测。
    """
    try:
        cur.execute(ddl)
        logger.info("已为旧表 %s 补充列 %s", table, column)
    except pymysql.err.OperationalError as exc:
        if exc.args and exc.args[0] == 1060:
            return
        raise


def init_schema_and_seed() -> None:
    """幂等建表并写入种子班级/课程（按名称去重）。"""
    from .db import db_cursor

    with db_cursor(commit=True) as cur:
        for ddl in _load_ddl_statements():
            cur.execute(ddl)
        logger.info("数据表结构已初始化（幂等）")

        _ensure_column(
            cur,
            table="questions",
            column="score",
            ddl="ALTER TABLE questions ADD COLUMN score INT NOT NULL DEFAULT 5 "
                "COMMENT '本题分值' AFTER analysis",
        )

        cur.executemany(
            "INSERT IGNORE INTO classes (name, grade, remark) VALUES (%s, %s, %s)",
            SEED_CLASSES,
        )
        cur.executemany(
            "INSERT IGNORE INTO courses (name, major, remark) VALUES (%s, %s, %s)",
            SEED_COURSES,
        )
        logger.info(
            "种子数据已确认：%s 个班级、%s 门课程",
            len(SEED_CLASSES), len(SEED_COURSES),
        )


def bootstrap(config) -> None:
    wait_for_database(config)
    init_schema_and_seed()
