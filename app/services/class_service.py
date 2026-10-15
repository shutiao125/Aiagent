"""班级业务服务。"""
from __future__ import annotations

from ..models.class_dao import ClassDao
from ..response import BizError, ErrorCode
from ..utils.serialization import to_jsonable


class ClassService:
    def __init__(self):
        self.dao = ClassDao()

    def list_classes(self) -> list[dict]:
        return [to_jsonable(r) for r in self.dao.list_all()]

    def get_class(self, class_id: int) -> dict:
        row = self.dao.get(class_id)
        if row is None:
            raise BizError("班级不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        return to_jsonable(row)

    def create_class(self, payload: dict) -> dict:
        name, grade, remark = self._read_payload(payload)
        if self.dao.get_by_name(name) is not None:
            raise BizError(f"班级「{name}」已存在，请勿重复添加")
        class_id = self.dao.insert(name, grade, remark)
        return self.get_class(class_id)

    def update_class(self, class_id: int, payload: dict) -> dict:
        if self.dao.get(class_id) is None:
            raise BizError("班级不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        name, grade, remark = self._read_payload(payload)
        if self.dao.get_by_name(name, exclude_id=class_id) is not None:
            raise BizError(f"班级「{name}」已存在，请勿重复添加")
        self.dao.update(class_id, name, grade, remark)
        return self.get_class(class_id)

    def delete_class(self, class_id: int) -> None:
        if self.dao.get(class_id) is None:
            raise BizError("班级不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        if self.dao.count_assignments(class_id) > 0:
            raise BizError("该班级下仍有作业，请先删除相关作业后再删除班级")
        self.dao.delete(class_id)

    @staticmethod
    def _read_payload(payload: dict) -> tuple[str, str, str]:
        if not isinstance(payload, dict):
            raise BizError("请求体格式错误")
        name = (payload.get("name") or "").strip()
        if not name:
            raise BizError("班级名称不能为空")
        if len(name) > 50:
            raise BizError("班级名称不能超过 50 字")
        grade = (payload.get("grade") or "").strip()[:20]
        remark = (payload.get("remark") or "").strip()[:200]
        return name, grade, remark
