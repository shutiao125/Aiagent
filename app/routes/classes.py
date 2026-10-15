"""班级管理路由：仅做参数提取与声明式服务绑定。"""
from __future__ import annotations

from flask import Blueprint, request

from ..response import ok
from ..services import Services

bp = Blueprint("classes", __name__, url_prefix="/api/classes")


@bp.get("")
def list_classes():
    return ok(Services.classes.list_classes())


@bp.post("")
def create_class():
    return ok(Services.classes.create_class(request.get_json(silent=True) or {}))


@bp.put("/<int:class_id>")
def update_class(class_id: int):
    return ok(Services.classes.update_class(class_id, request.get_json(silent=True) or {}))


@bp.delete("/<int:class_id>")
def delete_class(class_id: int):
    Services.classes.delete_class(class_id)
    return ok(None, message="删除成功")
