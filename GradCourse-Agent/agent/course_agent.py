import json
from agent.llm import chat
from agent.parser import parse_request

SYSTEM = """你是 GradCourse-Agent 的研究生智能选课 Agent。\n你必须使用工具获取课程与课表信息，不能凭空创造课程。\n硬约束：课程编码、校区、核心/专业课数量、时间冲突由程序判断。\n软约束：方向匹配、开卷偏好、避免某天上课等可按用户优先级优化。\n当工具返回无解或约束冲突时，你必须解释冲突，并主动调整软约束后重新规划。\n最终回答必须简洁、结构化：推荐课程、总学分、核心/专业课数量、时间风险、为什么这样选、如果放宽了什么约束。"""

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "search_courses", "description": "按课程方向和校区检索候选课程。",
      "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "campus": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_schedule", "description": "查询课程真实周次、星期、节次、教室、考试方式。",
      "parameters": {"type": "object", "properties": {"course_codes": {"type": "array", "items": {"type": "string"}}}, "required": ["course_codes"]}}},
    {"type": "function", "function": {"name": "check_conflict", "description": "按周次+星期+节次检查课程冲突。",
      "parameters": {"type": "object", "properties": {"course_codes": {"type": "array", "items": {"type": "string"}}}, "required": ["course_codes"]}}},
    {"type": "function", "function": {"name": "optimize_courses", "description": "在硬约束和软约束下自动组合课程；必要时可放宽开卷偏好。",
      "parameters": {"type": "object", "properties": {"keywords": {"type": "string"}, "campus": {"type": "string"}, "exam_preference": {"type": "string"}, "min_core": {"type": "integer"}, "min_prof": {"type": "integer"}, "total_credits": {"type": "number"}, "avoid_days": {"type": "array", "items": {"type": "string"}}, "excluded_codes": {"type": "array", "items": {"type": "string"}}}}}},
]


class CourseAgent:
    def __init__(self, tools, retriever=None, max_steps=6):
        self.tools = tools
        self.retriever = retriever
        self.max_steps = max_steps

    def answer(self, query, defaults=None):
        defaults = defaults or {}
        # 支持多轮调整：从当前会话传入已排除课程。
        constraints = parse_request(query, defaults)
        q_lower = str(query).lower()
        if defaults.get("current_courses"):
            for item in defaults["current_courses"]:
                if str(item.get("name", "")).lower() in q_lower and any(x in q_lower for x in ["删除", "不要", "换掉", "去掉"]):
                    constraints["excluded_codes"].append(str(item.get("code")))
        trace = []
        # First deterministic planning pass guarantees a useful result even if LLM fails.
        candidates, meta = self.tools.optimize(**constraints)
        trace.append({"step": 1, "action": "optimize_courses", "result": f"得到 {len(candidates)} 门候选，硬约束满足={meta.get('hard_constraints_satisfied')}"})
        # 软约束自动放宽：学位课数量和时间冲突绝不放宽；“只选开卷”在无解时可退化为“开卷优先”。
        if not meta.get("hard_constraints_satisfied") and constraints.get("exam_preference") == "只选开卷":
            relaxed = dict(constraints)
            relaxed["exam_preference"] = "开卷优先"
            alt, alt_meta = self.tools.optimize(**relaxed)
            trace.append({"step": 2, "action": "relax_exam_preference", "result": f"严格开卷无解，尝试开卷优先：硬约束满足={alt_meta.get('hard_constraints_satisfied')}"})
            if alt_meta.get("hard_constraints_satisfied") and len(alt) >= len(candidates):
                alt_meta.setdefault("warnings", []).append("严格开卷无法形成完整方案，已将‘只选开卷’放宽为‘开卷优先’。")
                candidates, meta = alt, alt_meta
                constraints = relaxed

        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps({"需求": query, "约束": constraints, "初始方案": candidates.to_dict("records"), "约束结果": meta}, ensure_ascii=False)},
        ]

        for step in range(2, self.max_steps + 1):
            msg = chat(messages, tools=TOOLS_SCHEMA, tool_choice="auto")
            if not msg:
                break
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return {"text": msg.get("content", ""), "trace": trace, "constraints": constraints, "courses": candidates, "meta": meta}
            messages.append(msg)
            for call in tool_calls:
                name = call["function"]["name"]
                args = json.loads(call["function"].get("arguments") or "{}")
                trace.append({"step": step, "action": name, "args": args})
                result = self._dispatch(name, args, constraints)
                if isinstance(result, tuple):
                    data, result_meta = result
                    payload = {"courses": data.to_dict("records"), "meta": result_meta}
                    if name == "optimize_courses":
                        candidates, meta = data, result_meta
                elif hasattr(result, "to_dict"):
                    payload = {"records": result.to_dict("records")}
                else:
                    payload = result
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(payload, ensure_ascii=False)[:12000]})

        return {"text": self._fallback(candidates, meta, constraints), "trace": trace, "constraints": constraints, "courses": candidates, "meta": meta}

    def _dispatch(self, name, args, constraints):
        if name == "search_courses": return self.tools.search_courses(**args).head(20)
        if name == "get_schedule": return self.tools.get_schedule(args.get("course_codes", []))
        if name == "check_conflict": return self.tools.check_conflict(args.get("course_codes", []))
        if name == "optimize_courses":
            merged = dict(constraints); merged.update(args)
            return self.tools.optimize(**merged)
        return {"error": f"unknown tool: {name}"}

    @staticmethod
    def _fallback(courses, meta, c):
        lines = ["## 智能选课方案", ""]
        lines.append(f"**校区：** {c['campus']}  | **考试偏好：** {c['exam_preference']}")
        lines.append(f"**核心课：** {meta.get('core_count', 0)} / {c['min_core']}  | **专业课：** {meta.get('professional_count', 0)} / {c['min_prof']}  | **学分：** {meta.get('credits', 0):.1f}")
        if courses.empty:
            lines.append("\n> 当前硬约束下没有可行课程组合，请降低一个软约束（例如把‘只选开卷’改为‘开卷优先’）。")
        else:
            for _, r in courses.iterrows():
                lines.append(f"- **{r['课程名称']}** `{r['课程编码']}`｜{r['开课校区']}｜{r['课程属性']}｜{r['学分']}学分｜{r['考试方式']}｜{r['星期节次']}")
        if meta.get("warnings"):
            lines.append("\n### 约束提示")
            lines.extend(f"- {w}" for w in meta["warnings"])
        return "\n".join(lines)
