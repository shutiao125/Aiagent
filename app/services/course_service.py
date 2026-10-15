"""专业课程业务服务。"""
from __future__ import annotations

from ..models.course_dao import CourseDao
from ..response import BizError, ErrorCode
from ..utils.serialization import to_jsonable


class CourseService:
    def __init__(self):
        self.dao = CourseDao()

    def list_courses(self) -> list[dict]:
        return [to_jsonable(r) for r in self.dao.list_all()]

    def get_course(self, course_id: int) -> dict:
        row = self.dao.get(course_id)
        if row is None:
            raise BizError("课程不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        return to_jsonable(row)

    def create_course(self, payload: dict) -> dict:
        name, major, remark = self._read_payload(payload)
        if self.dao.get_by_name(name) is not None:
            raise BizError(f"课程「{name}」已存在，请勿重复添加")
        course_id = self.dao.insert(name, major, remark)
        return self.get_course(course_id)

    def update_course(self, course_id: int, payload: dict) -> dict:
        if self.dao.get(course_id) is None:
            raise BizError("课程不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        name, major, remark = self._read_payload(payload)
        if self.dao.get_by_name(name, exclude_id=course_id) is not None:
            raise BizError(f"课程「{name}」已存在，请勿重复添加")
        self.dao.update(course_id, name, major, remark)
        return self.get_course(course_id)

    def delete_course(self, course_id: int) -> None:
        if self.dao.get(course_id) is None:
            raise BizError("课程不存在", code=ErrorCode.NOT_FOUND, http_status=404)
        if self.dao.count_assignments(course_id) > 0:
            raise BizError("该课程下仍有作业，请先删除相关作业后再删除课程")
        self.dao.delete(course_id)

    @staticmethod
    def _read_payload(payload: dict) -> tuple[str, str, str]:
        if not isinstance(payload, dict):
            raise BizError("请求体格式错误")
        name = (payload.get("name") or "").strip()
        if not name:
            raise BizError("课程名称不能为空")
        if len(name) > 80:
            raise BizError("课程名称不能超过 80 字")
        major = (payload.get("major") or "").strip()[:80]
        remark = (payload.get("remark") or "").strip()[:200]
        return name, major, remark
