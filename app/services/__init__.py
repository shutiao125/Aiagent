"""声明式业务服务注册中心。

约定（NFR-1）：
- 全部业务规则只在 service 层实现；
- 路由层通过 ``Services.<服务>.<操作>`` 显式（声明式）绑定调用，
  路由自身只负责参数提取与响应包装，不写业务逻辑、不出现 SQL；
- 数据访问统一经 models(DAO) 层完成。
"""
from __future__ import annotations

from .assignment_service import AssignmentService
from .chat_service import ChatService
from .class_service import ClassService
from .completion_service import CompletionService
from .course_service import CourseService
from .generation_service import GenerationService
from .grading_service import GradingService
from .message_service import MessageService
from .submission_service import SubmissionService


class Services:
    """业务服务单例注册表，路由层只依赖本对象。"""

    classes: ClassService = ClassService()
    courses: CourseService = CourseService()
    assignments: AssignmentService = AssignmentService()
    generation: GenerationService = GenerationService()
    submissions: SubmissionService = SubmissionService()
    grading: GradingService = GradingService()
    chats: ChatService = ChatService()
    messages: MessageService = MessageService()
    completions: CompletionService = CompletionService()


__all__ = ["Services"]
