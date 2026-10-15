"""Flask 应用工厂。"""
from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from .config import Config
from .db import init_pool
from .response import BizError, ErrorCode, fail


def create_app(config_object=Config) -> Flask:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    app = Flask(__name__, static_folder="../static", static_url_path="")
    app.config.from_object(config_object)
    CORS(app)

    # 1) 等待数据库就绪并建库 → 2) 初始化连接池 → 3) 幂等建表/种子数据
    from . import bootstrap
    bootstrap.wait_for_database(config_object)
    init_pool(config_object)
    bootstrap.init_schema_and_seed()

    # 4) 统一注册全部路由（含声明式服务绑定）
    from .routes import register_routes
    register_routes(app)

    @app.errorhandler(BizError)
    def handle_biz_error(exc: BizError):
        return fail(
            exc.message, code=exc.code, http_status=exc.http_status, data=exc.data
        )

    @app.errorhandler(404)
    def handle_404(_err):
        from flask import request
        if request.path.startswith("/api/"):
            return fail("接口不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        return fail("资源不存在", code=ErrorCode.NOT_FOUND, http_status=404)

    @app.errorhandler(Exception)
    def handle_exception(exc: Exception):
        logging.getLogger(__name__).exception("未处理异常: %s", exc)
        return fail("服务内部错误，请稍后重试", code=ErrorCode.INTERNAL_ERROR, http_status=500)

    return app
