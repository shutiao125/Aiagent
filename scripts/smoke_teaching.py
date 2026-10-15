"""AI 辅助教学系统后端冒烟测试（进程内直连 service 层，无需启动 Flask）。

覆盖：
- 班级 / 课程 CRUD、重名校验、被作业引用时禁止删除；
- 作业 + 五种题型题目创建、详情、题目增改删、作业逻辑删除；
- AI 生成（强制 MOCK 模式）参数校验、落库与题量；
- 答疑对话普通 + 流式回归（确认无拦截分支）；
- 首页统计。

用法：.venv 虚拟环境下运行 python scripts/smoke_teaching.py
"""
from __future__ import annotations

import os
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.bootstrap import init_schema_and_seed
from app.config import Config
from app.db import init_pool
from app.response import BizError
from app.services import Services

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    print(f"[{PASS if condition else FAIL}] {name} {detail}")


def expect_biz(name: str, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except BizError as exc:
        check(name, True, f"→ {exc.message}")
    else:
        check(name, False, "未抛出 BizError")


def main() -> int:
    init_pool(Config)
    init_schema_and_seed()

    classes_svc = Services.classes
    courses_svc = Services.courses
    assignments_svc = Services.assignments
    chats_svc = Services.chats

    tag = str(int(time.time()))
    class_name = f"冒烟测试班{tag}"
    course_name = f"冒烟测试课程{tag}"

    # ---------- 1. 班级 / 课程 ----------
    klass = classes_svc.create_class({"name": class_name, "grade": "2023级", "remark": "冒烟"})
    check("班级创建", klass["name"] == class_name, f"id={klass['id']}")
    expect_biz("班级重名拒绝", classes_svc.create_class, {"name": class_name})

    course = courses_svc.create_course({"name": course_name, "major": "测试专业", "remark": "冒烟"})
    check("课程创建", course["name"] == course_name, f"id={course['id']}")
    expect_biz("课程重名拒绝", courses_svc.create_course, {"name": course_name})

    classes_svc.update_class(klass["id"], {"name": class_name + "改", "grade": "2024级", "remark": ""})
    check("班级改名", classes_svc.get_class(klass["id"])["grade"] == "2024级")
    classes_svc.update_class(klass["id"], {"name": class_name, "grade": "2023级", "remark": "冒烟"})

    # ---------- 2. 手动建作业（五种题型） ----------
    payload = {
        "title": f"{course_name}第一次作业",
        "class_id": klass["id"],
        "course_id": course["id"],
        "difficulty": 2,
        "requirement": "覆盖五种题型",
        "questions": [
            {"type": "single", "stem": "单选：1+1=?",
             "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"},
                         {"key": "C", "content": "3"}, {"key": "D", "content": "4"}],
             "answer": "B", "analysis": "基础运算"},
            {"type": "multiple", "stem": "多选：下列为偶数的是？",
             "options": [{"key": "A", "content": "2"}, {"key": "B", "content": "3"},
                         {"key": "C", "content": "4"}, {"key": "D", "content": "5"}],
             "answer": "AC", "analysis": "2 和 4 是偶数"},
            {"type": "judge", "stem": "判断：1+1=2。", "answer": "A", "analysis": ""},
            {"type": "fill", "stem": "填空：1+1=____。", "answer": "2", "analysis": ""},
            {"type": "short", "stem": "简答：简述加法含义。", "answer": "把两个数合并成一个数的运算。", "analysis": ""},
        ],
    }
    assignment = assignments_svc.create_assignment(payload)
    aid = assignment["id"]
    check("作业创建含5题", len(assignment["questions"]) == 5,
          f"题数={len(assignment['questions'])} source 应为 manual")
    check("作业来源 manual", assignment["source"] == "manual")
    check("判断题选项自动补全",
          next(q for q in assignment["questions"] if q["type"] == "judge")["options"][0]["content"] == "正确")
    check("题目序号连续", [q["seq"] for q in assignment["questions"]] == [1, 2, 3, 4, 5])
    check("题型中文标签", assignment["questions"][0]["type_label"] == "单选题")

    # 非法题目
    expect_biz("题干为空拒绝",
               assignments_svc.add_question, aid, {"type": "single", "stem": "  ", "answer": "A"})
    expect_biz("非法题型拒绝",
               assignments_svc.add_question, aid, {"type": "essay", "stem": "xx", "answer": "x"})
    expect_biz("选择题答案越界拒绝",
               assignments_svc.add_question, aid,
               {"type": "single", "stem": "xx",
                "options": [{"key": "A", "content": "a"}, {"key": "B", "content": "b"}],
                "answer": "C"})
    expect_biz("空班级ID拒绝", assignments_svc.create_assignment,
               {"title": "x", "course_id": course["id"]})
    expect_biz("不存在的班级拒绝", assignments_svc.create_assignment,
               {"title": "x", "class_id": 99999999, "course_id": course["id"]})

    # 引用校验
    expect_biz("班级被作业引用禁止删除", classes_svc.delete_class, klass["id"])
    expect_biz("课程被作业引用禁止删除", courses_svc.delete_course, course["id"])

    # 题目增改删
    q = assignments_svc.add_question(aid, {
        "type": "fill", "stem": "追加填空题：2+2=____", "answer": "4",
    })
    check("追加题目", q["seq"] == 6, f"seq={q['seq']}")
    updated = assignments_svc.update_question(q["id"], {
        "type": "fill", "stem": "追加填空题（改）：2+3=____", "answer": "5",
    })
    check("修改题目", updated["stem"].endswith("2+3=____") and updated["answer"] == "5")
    assignments_svc.delete_question(q["id"])
    check("删除题目", len(assignments_svc.get_assignment_detail(aid)["questions"]) == 5)

    # 作业更新
    assignments_svc.update_assignment(aid, {
        "title": payload["title"] + "（改）",
        "class_id": klass["id"], "course_id": course["id"],
        "difficulty": 3, "requirement": "改",
    })
    check("作业难度更新", assignments_svc.get_assignment_detail(aid)["difficulty"] == 3)

    # 列表过滤
    lst = assignments_svc.list_assignments(class_id=klass["id"])
    check("按班级筛选列表", any(a["id"] == aid for a in lst) and all(a["class_id"] == klass["id"] for a in lst))
    lst_kw = assignments_svc.list_assignments(keyword="冒烟测试课程")
    check("关键词筛选列表", any(a["id"] == aid for a in lst_kw))

    # ---------- 3. AI 生成（强制 MOCK） ----------
    gen = Services.generation
    gen.config = types.SimpleNamespace(MOCK_LLM=True)

    expect_biz("题型数量全为0拒绝", gen.generate,
               {"class_id": klass["id"], "course_id": course["id"],
                "counts": {"single": 0, "multiple": 0, "judge": 0, "fill": 0, "short": 0}})
    expect_biz("总数超30拒绝", gen.generate,
               {"class_id": klass["id"], "course_id": course["id"],
                "counts": {"single": 31}})

    result = gen.generate({
        "class_id": klass["id"], "course_id": course["id"], "difficulty": 1,
        "requirement": "冒烟生成", "title": "",
        "counts": {"single": 2, "multiple": 1, "judge": 1, "fill": 1, "short": 1},
    })
    check("MOCK 生成6题落库", result["question_count"] == 6, f"dropped={result['dropped_count']}")
    gen_detail = assignments_svc.get_assignment_detail(result["assignment_id"])
    check("生成作业来源 ai", gen_detail["source"] == "ai")
    check("默认标题含课程名", course_name in result["title"], result["title"])
    check("生成题目顺序",
          [q["type"] for q in gen_detail["questions"]] ==
          ["single", "single", "multiple", "judge", "fill", "short"])

    # 解析器鲁棒性
    parse = Services.generation._parse_json
    parsed = parse('前缀文字 ```json\n{"questions":[{"type":"short","stem":"x","answer":"y"}]}\n``` 后缀')
    check("JSON 围栏剥离解析", len(parsed) == 1 and parsed[0]["type"] == "short")
    expect_biz("非JSON输出报错", parse, "抱歉我不能生成")

    # ---------- 4. 答疑对话回归（MOCK，无拦截） ----------
    comp_cfg = types.SimpleNamespace(
        MOCK_LLM=True, SYSTEM_PROMPT="测试", CONTEXT_LIMIT=20, TITLE_MAX_LEN=20,
    )
    # 强制重置 LLM 单例为 MOCK
    import app.llm as llm_pkg
    llm_pkg._client = None
    from app.services.completion_service import CompletionService
    comp = CompletionService(config=comp_cfg)

    chat = chats_svc.create_chat()
    cid = chat["id"]
    reply = comp.reply_once(cid, "你好，解释一下什么是递归", False)
    check("普通对话返回", reply["status"] == "ok" and bool(reply["content"]))
    history = Services.messages.history(cid)
    check("消息正常落库无 blocked",
          all(m["status"] == "normal" for m in history) and len(history) == 2)
    auto_title = chats_svc.get_chat(cid)["title"]
    check("首轮自动命名", auto_title != "新会话", auto_title)

    events = list(comp.stream_reply(cid, "再来一个问题", False))
    event_names = []
    for chunk in events:
        for line in chunk.strip().splitlines():
            if line.startswith("event: "):
                event_names.append(line[7:])
    check("流式含 meta/delta/done",
          "meta" in event_names and "delta" in event_names and event_names[-1] == "done")
    check("流式无 blocked 事件", "blocked" not in event_names, str(event_names))
    chats_svc.delete_chat(cid)

    # ---------- 5. 学生提交 + AI/教师批改 ----------
    sub_svc = Services.submissions
    sub_svc.grading.config = types.SimpleNamespace(MOCK_LLM=True)

    grade_assignment = assignments_svc.create_assignment({
        "title": f"{course_name}批改测试作业",
        "class_id": klass["id"], "course_id": course["id"],
        "difficulty": 2, "requirement": "",
        "questions": [
            {"type": "single", "stem": "单选：1+1=?",
             "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"},
                         {"key": "C", "content": "3"}, {"key": "D", "content": "4"}],
             "answer": "B", "analysis": "", "score": 5},
            {"type": "multiple", "stem": "多选：偶数有？",
             "options": [{"key": "A", "content": "2"}, {"key": "B", "content": "3"},
                         {"key": "C", "content": "4"}, {"key": "D", "content": "5"}],
             "answer": "AC", "analysis": "", "score": 10},
            {"type": "judge", "stem": "判断：1+1=2。", "answer": "A", "score": 5},
            {"type": "fill", "stem": "填空：1+1=____。", "answer": "2", "score": 5},
            {"type": "short", "stem": "简答：简述加法。", "answer": "合并运算", "score": 10},
        ],
    })
    gaid = grade_assignment["id"]
    qids = [q["id"] for q in grade_assignment["questions"]]

    # 试卷不泄露答案
    paper = sub_svc.get_paper(gaid)
    check("试卷满分=35", paper["max_score"] == 35, str(paper["max_score"]))
    check("试卷不下发答案", all("answer" not in q and "analysis" not in q for q in paper["questions"]))

    submit_payload = {
        "student_name": "张三", "student_no": f"E{tag}",
        "answers": [
            {"question_id": qids[0], "response": "B"},      # 单选 对 5
            {"question_id": qids[1], "response": "ca"},     # 多选（乱序）对 10
            {"question_id": qids[2], "response": "A"},      # 判断 对 5
            {"question_id": qids[3], "response": "2"},      # 填空（MOCK精确）对 5
            {"question_id": qids[4], "response": "加法就是把两个数合并"},  # 简答待批
        ],
    }
    submit_result = sub_svc.submit(gaid, submit_payload)
    sid = submit_result["submission_id"]
    check("含主观题提交后待批", submit_result["status"] == "pending", str(submit_result))
    check("客观题自动批已得25", submit_result["total_score"] == 25, str(submit_result["total_score"]))
    check("待批计数>0", sub_svc.pending_count() >= 1)
    expect_biz("重复学号拒绝提交", sub_svc.submit, gaid, submit_payload)
    expect_biz("缺姓名拒绝提交", sub_svc.submit, gaid,
               {"student_no": "X1", "answers": []})

    detail = sub_svc.get_detail(sid)
    short_answer = next(a for a in detail["answers"] if a["type"] == "short")
    objective_rows = [a for a in detail["answers"] if a["type"] != "short"]
    check("客观题全部 AI 判对", all(a["is_correct"] == 1 and a["grader"] == "ai" for a in objective_rows))
    check("主观题待批", short_answer["is_correct"] is None and short_answer["got_score"] is None)
    check("待批列表含该提交", any(s["id"] == sid for s in sub_svc.list_grading(status="pending")))

    # 填空答错 → 0 分（严格规则）
    wrong = sub_svc.submit(gaid, {
        "student_name": "李四", "student_no": f"E{tag}B",
        "answers": [
            {"question_id": qids[0], "response": "C"},
            {"question_id": qids[1], "response": "AC"},
            {"question_id": qids[2], "response": "A"},
            {"question_id": qids[3], "response": "3"},
            {"question_id": qids[4], "response": "答了"},
        ],
    })
    sid2 = wrong["submission_id"]
    d2 = sub_svc.get_detail(sid2)
    wrong_single = next(a for a in d2["answers"] if a["type"] == "single")
    wrong_fill = next(a for a in d2["answers"] if a["type"] == "fill")
    check("单选答错0分", wrong_single["is_correct"] == 0 and wrong_single["got_score"] == 0)
    check("填空答错0分且判错", wrong_fill["is_correct"] == 0 and wrong_fill["got_score"] == 0)

    # 老师批改：简答给 8 分（李四的全批完→graded）
    short2 = next(a for a in d2["answers"] if a["type"] == "short")
    sub_svc.save_teacher_grade(sid2, {"grades": [
        {"answer_id": short2["answer_id"], "is_correct": 1, "score": 8, "comment": "要点基本完整"},
    ]})
    d2b = sub_svc.get_detail(sid2)
    check("教师批完主观题→graded", d2b["status"] == "graded", d2b["status"])
    check("总分=23(多选10+判断5+简答8，单选/填空0)", d2b["total_score"] == 23, str(d2b["total_score"]))
    check("已批列表含李四", any(s["id"] == sid2 for s in sub_svc.list_grading(status="graded")))
    check("教师批改grader标记",
          sub_svc.get_detail(sid2)["answers"][-1]["grader"] == "teacher")

    # 老师覆盖 AI 判分（张三简答批完 + 改填空分数）
    fill_answer = next(a for a in detail["answers"] if a["type"] == "fill")
    sub_svc.save_teacher_grade(sid, {"grades": [
        {"answer_id": short_answer["answer_id"], "is_correct": 1, "score": 9, "comment": "好"},
        {"answer_id": fill_answer["answer_id"], "is_correct": 0, "score": 0, "comment": "老师复核有误"},
    ]})
    d1b = sub_svc.get_detail(sid)
    check("覆盖AI后总分=29(25-5+9)", d1b["total_score"] == 29, str(d1b["total_score"]))
    check("张三状态graded", d1b["status"] == "graded")
    expect_biz("越界得分拒绝", sub_svc.save_teacher_grade, sid,
               {"grades": [{"answer_id": short_answer["answer_id"], "score": 99}]})

    # 全客观题作业：提交即 graded
    obj_only = assignments_svc.create_assignment({
        "title": f"{course_name}全客观作业",
        "class_id": klass["id"], "course_id": course["id"],
        "difficulty": 1, "requirement": "",
        "questions": [
            {"type": "single", "stem": "2+2=?",
             "options": [{"key": "A", "content": "3"}, {"key": "B", "content": "4"}],
             "answer": "B", "score": 5},
            {"type": "fill", "stem": "填空：2+2=____", "answer": "4", "score": 5},
        ],
    })
    oq = [q["id"] for q in obj_only["questions"]]
    r3 = sub_svc.submit(obj_only["id"], {
        "student_name": "王五", "student_no": f"E{tag}C",
        "answers": [{"question_id": oq[0], "response": "B"},
                    {"question_id": oq[1], "response": "4"}],
    })
    check("全客观题提交即已批", r3["status"] == "graded" and r3["total_score"] == 10, str(r3))

    # 清理提交相关脏数据
    from app.db import execute
    for s_id in (sid, sid2, r3["submission_id"]):
        execute("DELETE FROM submission_answers WHERE submission_id = %s", (s_id,), commit=True)
        execute("DELETE FROM submissions WHERE id = %s", (s_id,), commit=True)
    assignments_svc.delete_assignment(gaid)
    assignments_svc.delete_assignment(obj_only["id"])
    check("提交/批改脏数据已清理", True)

    # ---------- 6. 首页统计 ----------
    board = assignments_svc.dashboard()
    check("首页统计四项计数",
          all(k in board for k in ("class_count", "course_count",
                                    "assignment_count", "question_count")))
    check("最近作业列表", isinstance(board["recent_assignments"], list))

    # ---------- 清理脏数据 ----------
    assignments_svc.delete_assignment(aid)
    assignments_svc.delete_assignment(result["assignment_id"])
    classes_svc.delete_class(klass["id"])
    courses_svc.delete_course(course["id"])
    check("冒烟数据清理完成", True)

    failed = [r for r in results if not r[1]]
    print(f"\n===== 结果：{len(results) - len(failed)}/{len(results)} 通过 =====")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
