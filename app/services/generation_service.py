"""AI 作业生成编排：班级/课程/题型要求 → LLM 结构化 JSON → 校验落库。"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from ..config import Config
from ..db import db_cursor
from ..llm import get_llm_client
from ..llm.base import LLMConfigError
from ..models.class_dao import ClassDao
from ..models.course_dao import CourseDao
from ..response import BizError, ErrorCode
from .assignment_service import AssignmentService

logger = logging.getLogger(__name__)

TYPE_LABELS = {
    "single": "单选题",
    "multiple": "多选题",
    "judge": "判断题",
    "fill": "填空题",
    "short": "简答题",
}
DIFFICULTY_LABELS = {1: "简单", 2: "中等", 3: "困难"}
MAX_TOTAL = 30


class GenerationService:
    def __init__(self, config=Config):
        self.config = config
        self.class_dao = ClassDao()
        self.course_dao = CourseDao()
        self.assignment_service = AssignmentService()

    def generate(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise BizError("请求体格式错误")

        try:
            class_id = int(payload.get("class_id"))
            course_id = int(payload.get("course_id"))
        except (TypeError, ValueError):
            raise BizError("请选择班级与课程")
        klass = self.class_dao.get(class_id)
        course = self.course_dao.get(course_id)
        if klass is None:
            raise BizError("所选班级不存在，请重新选择")
        if course is None:
            raise BizError("所选课程不存在，请重新选择")

        try:
            difficulty = int(payload.get("difficulty", 2))
        except (TypeError, ValueError):
            difficulty = 2
        if difficulty not in (1, 2, 3):
            raise BizError("难度取值无效")
        requirement = (payload.get("requirement") or "").strip()
        title = (payload.get("title") or "").strip()[:150]
        counts = self._read_counts(payload.get("counts"))

        if getattr(self.config, "MOCK_LLM", False):
            raw_questions = self._mock_questions(course["name"], counts, difficulty)
        else:
            raw_questions = self._call_llm(
                course["name"], klass["name"], difficulty, requirement, counts
            )

        # 逐题归一化校验，丢弃非法题并计数
        questions: list[dict] = []
        dropped = 0
        for item in raw_questions:
            try:
                questions.append(self.assignment_service._normalize_question(item))
            except BizError:
                dropped += 1
        if not questions:
            logger.warning("AI 生成结果全部未通过校验，原始返回：%s", str(raw_questions)[:500])
            raise BizError("生成结果解析失败，请调整要求后重试", code=ErrorCode.LLM_ERROR, http_status=502)
        if dropped:
            logger.info("AI 生成 %s 题，丢弃非法题 %s 道", len(questions), dropped)

        if not title:
            title = f"{course['name']}作业·{datetime.now().strftime('%m月%d日')}"

        with db_cursor(commit=True) as cur:
            from ..models.assignment_dao import AssignmentDao
            assignment_id = AssignmentDao().insert(
                title, class_id, course_id, difficulty, requirement, "ai", cur=cur
            )
            from ..models.question_dao import QuestionDao
            QuestionDao().batch_insert(assignment_id, questions, cur=cur)

        return {
            "assignment_id": assignment_id,
            "title": title,
            "question_count": len(questions),
            "dropped_count": dropped,
        }

    # ---------- 参数 ----------
    @staticmethod
    def _read_counts(raw) -> dict[str, int]:
        if not isinstance(raw, dict):
            raise BizError("请选择题型与数量")
        counts: dict[str, int] = {}
        for qtype in TYPE_LABELS:
            try:
                n = int(raw.get(qtype, 0) or 0)
            except (TypeError, ValueError):
                n = 0
            counts[qtype] = max(0, n)
        total = sum(counts.values())
        if total == 0:
            raise BizError("请至少填写一种题型的数量")
        if total > MAX_TOTAL:
            raise BizError(f"单次生成题目总数不能超过 {MAX_TOTAL} 道")
        return counts

    # ---------- 真实 LLM ----------
    def _call_llm(self, course_name: str, class_name: str, difficulty: int,
                  requirement: str, counts: dict[str, int]) -> list[dict]:
        type_desc = "、".join(
            f"{TYPE_LABELS[t]}{n}道" for t, n in counts.items() if n > 0
        )
        requirement_block = (
            f"\n- 知识点/出题要求：{requirement}" if requirement else ""
        )
        system_msg = (
            "你是一名经验丰富的高校命题教师，擅长为专业课程编写规范、无歧义、"
            "难度梯度合理的习题。你必须严格只输出 JSON，不要输出任何解释、"
            "前后缀文字或 Markdown 代码围栏。"
        )
        user_msg = f"""请为以下教学场景命制作业习题：
- 课程：{course_name}
- 授课班级：{class_name}
- 难度：{DIFFICULTY_LABELS[difficulty]}
- 题型与数量：{type_desc}{requirement_block}

输出 JSON 结构（questions 数组中题目顺序即题型顺序）：
{{
  "questions": [
    {{
      "type": "single",
      "stem": "题干文本",
      "options": [{{"key": "A", "content": "选项A内容"}}, {{"key": "B", "content": "..."}}],
      "answer": "A",
      "analysis": "解析（一句话说明考点）"
    }},
    {{
      "type": "multiple",
      "stem": "题干文本",
      "options": [{{"key": "A", "content": "..."}}, {{"key": "B", "content": "..."}}],
      "answer": "AC",
      "analysis": "解析"
    }},
    {{
      "type": "judge",
      "stem": "判断对错的陈述",
      "options": [{{"key": "A", "content": "正确"}}, {{"key": "B", "content": "错误"}}],
      "answer": "A",
      "analysis": "解析"
    }},
    {{
      "type": "fill",
      "stem": "带下划线空位的填空题干（用 ____ 表示空位）",
      "answer": "参考答案，多个空用分号分隔",
      "analysis": "评分要点"
    }},
    {{
      "type": "short",
      "stem": "简答题干",
      "answer": "参考答案/评分要点，分点表述",
      "analysis": "命题意图"
    }}
  ]
}}

硬性要求：
1. 只输出 JSON 本体，禁止输出 ```json 围栏及其它任何文字；
2. 单选题答案只能有 1 个选项键，多选题答案 2 个及以上；
3. 题目内容必须紧扣《{course_name}》课程，不得出现与课程无关的题目；
4. 选项 key 从 A 开始连续编号，每题 4 个选项（判断题固定 正确/错误）；
5. 题干、答案、解析均使用中文，内容准确无歧义。"""

        client = get_llm_client(self.config)
        try:
            content = client.chat(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                deep_thinking=False,
            )
        except LLMConfigError as exc:
            raise BizError(str(exc), code=ErrorCode.LLM_CONFIG, http_status=503) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("作业生成模型调用失败")
            raise BizError(f"模型调用失败：{exc}", code=ErrorCode.LLM_ERROR, http_status=502) from exc

        return self._parse_json(content)

    @staticmethod
    def _parse_json(content: str) -> list[dict]:
        if not content:
            raise BizError("模型返回为空，请重试", code=ErrorCode.LLM_ERROR, http_status=502)
        text = content.strip()
        # 去掉可能的 ```json ... ``` 围栏
        if text.startswith("```"):
            text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            logger.warning("模型输出未找到 JSON 对象：%s", content[:300])
            raise BizError("生成结果解析失败，请重试", code=ErrorCode.LLM_ERROR, http_status=502)
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            logger.warning("模型 JSON 解析失败：%s；原文：%s", exc, content[:300])
            raise BizError("生成结果解析失败，请重试", code=ErrorCode.LLM_ERROR, http_status=502) from exc
        questions = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(questions, list):
            raise BizError("生成结果格式不正确，请重试", code=ErrorCode.LLM_ERROR, http_status=502)
        return questions

    # ---------- MOCK 离线生成 ----------
    @staticmethod
    def _mock_questions(course_name: str, counts: dict[str, int],
                        difficulty: int) -> list[dict]:
        diff = DIFFICULTY_LABELS[difficulty]
        items: list[dict] = []

        def add(qtype: str, n: int) -> None:
            for i in range(1, n + 1):
                idx = len(items) + 1
                if qtype == "single":
                    items.append({
                        "type": "single",
                        "stem": f"【MOCK·{course_name}·{diff}】单选题 {idx}：下列关于{course_name}基本概念的说法，正确的是哪一项？",
                        "options": [
                            {"key": "A", "content": f"{course_name}的核心概念表述（参考答案项）"},
                            {"key": "B", "content": "与定义相反的错误表述"},
                            {"key": "C", "content": "混淆相近概念的干扰项"},
                            {"key": "D", "content": "以偏概全的干扰项"},
                        ],
                        "answer": "A",
                        "analysis": f"考查{course_name}基本概念的理解，A 项表述准确。",
                    })
                elif qtype == "multiple":
                    items.append({
                        "type": "multiple",
                        "stem": f"【MOCK·{course_name}】多选题 {idx}：以下属于{course_name}研究范畴的有哪几项？",
                        "options": [
                            {"key": "A", "content": "基本概念与定义"},
                            {"key": "B", "content": "典型方法与应用"},
                            {"key": "C", "content": "与本课程无关的内容"},
                            {"key": "D", "content": "常见性质与结论"},
                        ],
                        "answer": "ABD",
                        "analysis": "C 项不属于本课程范畴，其余均是。",
                    })
                elif qtype == "judge":
                    items.append({
                        "type": "judge",
                        "stem": f"【MOCK】判断题 {idx}：掌握{course_name}的基本概念是学习后续内容的基础。",
                        "options": [
                            {"key": "A", "content": "正确"},
                            {"key": "B", "content": "错误"},
                        ],
                        "answer": "A",
                        "analysis": "基本概念是课程学习的基础，表述正确。",
                    })
                elif qtype == "fill":
                    items.append({
                        "type": "fill",
                        "stem": f"【MOCK】填空题 {idx}：{course_name}中最基本的研究对象是 ____。",
                        "answer": f"{course_name}的基本概念（参考答案）",
                        "analysis": "考查课程最基础的研究对象。",
                    })
                else:
                    items.append({
                        "type": "short",
                        "stem": f"【MOCK】简答题 {idx}：请简述{course_name}中一个核心概念的含义及其应用场景。",
                        "answer": (
                            "评分要点：①准确定义核心概念（40%）；"
                            "②说明其关键性质（30%）；③举出一个实际应用场景（30%）。"
                        ),
                        "analysis": "考查概念理解与联系实际的能力，按要点酌情给分。",
                    })

        for qtype, n in counts.items():
            add(qtype, n)
        return items
