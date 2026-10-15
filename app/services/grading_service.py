"""客观题自动批改：选择/判断程序判分；填空题交 AI 严格语义判分。

规则（与用户确认）：
- 单选/多选/判断：与参考答案逐字符（多选忽略顺序）一致才满分，否则 0 分；
- 填空：AI 逐空语义比对，多空题任一空不一致即整题 0 分；
- AI 不可用/解析失败：填空题降级为待老师批改，不阻断提交。
"""
from __future__ import annotations

import json
import logging
import re

from ..config import Config
from ..llm import get_llm_client

logger = logging.getLogger(__name__)

CHOICE_TYPES = ("single", "multiple", "judge")


def _normalize_letters(text: str) -> str:
    """归一化选项字母：大写、去分隔符与空白、去重保序。"""
    letters = re.findall(r"[A-Za-z]", (text or "").upper())
    return "".join(dict.fromkeys(letters))


def _normalize_text(text: str) -> str:
    """填空答案文本归一化：去空白与常见标点、转小写，用于 MOCK 精确比对。"""
    return re.sub(r"[\s，。、；;,.．·:：!！?？（）()\[\]【】\"'`~_-]", "", (text or "")).lower()


def _split_blanks(text: str) -> list[str]:
    parts = re.split(r"[;；]", text or "")
    return [p.strip() for p in parts if p.strip()]


class GradingService:
    def __init__(self, config=Config):
        self.config = config

    # ---------- 选择 / 判断 ----------
    @staticmethod
    def grade_choice(question: dict, response: str) -> dict | None:
        """返回 {is_correct, score, comment}；无有效标准答案时返回 None（转人工）。"""
        reference = (question.get("answer") or "").strip()
        if not reference or not re.fullmatch(r"[A-Za-z，,；;\s]+", reference):
            return None
        qtype = question["type"]
        given = _normalize_letters(response)
        if not given:
            return {
                "is_correct": 0, "score": 0,
                "comment": "学生未作答，按错误处理。",
            }
        if qtype == "multiple":
            correct = set(_normalize_letters(reference))
            got = set(given)
            ok = got == correct and bool(correct)
        else:
            ok = given == _normalize_letters(reference)
        score = question["score"] if ok else 0
        comment = "回答正确。" if ok else f"回答错误，正确答案为 {_normalize_letters(reference)}。"
        return {"is_correct": 1 if ok else 0, "score": score, "comment": comment}

    # ---------- 填空（AI 批量判分） ----------
    def grade_fill_batch(self, items: list[dict]) -> dict[int, dict]:
        """items: [{question_id, stem, reference, response, score}]
        返回 {question_id: {is_correct, score, comment}}；降级项 is_correct=None。
        """
        if not items:
            return {}
        if getattr(self.config, "MOCK_LLM", False):
            return self._mock_fill(items)
        return self._llm_fill(items)

    @staticmethod
    def _mock_fill(items: list[dict]) -> dict[int, dict]:
        result: dict[int, dict] = {}
        for it in items:
            refs = _split_blanks(it["reference"]) or [it["reference"]]
            gots = _split_blanks(it["response"]) or [it["response"]]
            ok = len(gots) == len(refs) and all(
                _normalize_text(g) == _normalize_text(r) for g, r in zip(gots, refs)
            )
            result[it["question_id"]] = {
                "is_correct": 1 if ok else 0,
                "score": it["score"] if ok else 0,
                "comment": "回答正确。" if ok else "回答与参考答案不一致。",
            }
        return result

    def _llm_fill(self, items: list[dict]) -> dict[int, dict]:
        payload = [
            {
                "id": it["question_id"],
                "stem": it["stem"],
                "reference": it["reference"],
                "response": it["response"],
            }
            for it in items
        ]
        system_msg = (
            "你是严谨的填空题阅卷老师。逐空比对学生作答与参考答案是否语义一致，"
            "同义词、语序不同但含义相同可视为正确；多空题必须每一个空都正确，"
            "整题才判 correct=true，任意一个空错误或缺失则 correct=false。"
            "只输出 JSON，不要输出任何解释或 Markdown 围栏。"
        )
        user_msg = (
            "请批改以下填空题，严格输出 JSON：\n"
            '{"results":[{"id":题目id(整数),"correct":true或false,'
            '"reason":"简短中文评语（30字内）"}]}\n'
            f"题目数据：{json.dumps(payload, ensure_ascii=False)}"
        )
        fallback = {
            it["question_id"]: {
                "is_correct": None, "score": None,
                "comment": "AI 批改不可用，请老师人工批改。",
            }
            for it in items
        }
        try:
            content = get_llm_client(self.config).chat(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                deep_thinking=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI 填空批改调用失败，全部降级人工：%s", exc)
            return fallback

        parsed = self._parse(content)
        if parsed is None:
            return fallback

        by_id = {it["question_id"]: it for it in items}
        result: dict[int, dict] = {}
        for row in parsed:
            try:
                qid = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            it = by_id.get(qid)
            if it is None:
                continue
            ok = bool(row.get("correct"))
            reason = str(row.get("reason") or ("回答正确。" if ok else "回答与参考答案不一致。")).strip()
            result[qid] = {
                "is_correct": 1 if ok else 0,
                "score": it["score"] if ok else 0,
                "comment": reason[:200],
            }
        # 未覆盖到的题目同样降级
        for qid, it in by_id.items():
            result.setdefault(qid, fallback[qid])
        return result

    @staticmethod
    def _parse(content: str) -> list[dict] | None:
        if not content:
            return None
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1]
                if text.lstrip().lower().startswith("json"):
                    text = text.lstrip()[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            logger.warning("AI 填空批改 JSON 解析失败：%s", content[:300])
            return None
        rows = data.get("results") if isinstance(data, dict) else None
        return rows if isinstance(rows, list) else None
