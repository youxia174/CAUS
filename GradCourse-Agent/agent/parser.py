import re


def parse_request(text, defaults=None):
    defaults = defaults or {}
    q = str(text or "")
    campus = defaults.get("campus", "不限")
    if "玉泉路" in q: campus = "玉泉路"
    elif "雁栖湖" in q: campus = "雁栖湖"
    elif "中关村" in q: campus = "中关村"

    if any(x in q for x in ["全部开卷", "都开卷", "必须开卷", "只选开卷", "全是开卷"]):
        exam = "只选开卷"
    elif "开卷" in q:
        exam = "开卷优先"
    else:
        exam = defaults.get("exam_preference", "不限")

    min_core = int(defaults.get("min_core", 2))
    min_prof = int(defaults.get("min_prof", 2))
    total_credits = float(defaults.get("total_credits", 0))
    min_public_elective = int(defaults.get("min_public_elective", 0))
    avoid_days = list(defaults.get("avoid_days", []))
    avoid_days_hard = bool(defaults.get("avoid_days_hard", False))

    m = re.search(r"核心(?:课)?\s*(?:至少|不少于|>=|≥)\s*(\d+)\s*门", q)
    if m: min_core = int(m.group(1))
    m = re.search(r"专业(?:课)?\s*(?:至少|不少于|>=|≥)\s*(\d+)\s*门", q)
    if m: min_prof = int(m.group(1))
    m = re.search(r"(?:总学分|学分)\s*(?:至少|不少于|>=|≥)\s*(\d+(?:\.\d+)?)", q)
    if m: total_credits = float(m.group(1))
    if "公共选修" in q:
        m = re.search(r"公共选修(?:课)?\s*(?:至少|不少于|>=|≥)?\s*(\d+)?", q)
        min_public_elective = int(m.group(1) or 1) if m else 1
    for d in ["一", "二", "三", "四", "五", "六", "日"]:
        if f"周{d}" in q and any(w in q for w in ["不要", "不想", "不安排"]):
            if f"周{d}" not in avoid_days: avoid_days.append(f"周{d}")
            avoid_days_hard = True
        elif f"周{d}" in q and "尽量避免" in q:
            if f"周{d}" not in avoid_days: avoid_days.append(f"周{d}")

    keywords = []
    groups = {
        "人工智能": ["人工智能", "ai"], "机器学习": ["机器学习", "ml"],
        "深度学习": ["深度学习", "dl"], "大模型": ["大模型", "llm", "语言模型"],
        "自然语言": ["自然语言", "nlp"], "智能体": ["agent", "智能体"],
        "算法": ["算法"], "软件工程": ["软件工程"], "知识工程": ["知识工程"],
        "数据挖掘": ["数据挖掘"], "计算机": ["计算机"],
    }
    low = q.lower()
    for label, words in groups.items():
        if any(w in low for w in words): keywords.append(label)
    if "智能体" in keywords:
        keywords += ["人工智能", "大模型", "自然语言", "算法", "软件工程"]
    if not keywords:
        keywords = ["人工智能"]

    # Priority: explicit language changes soft weights, not hard requirements.
    priority = {"direction": 0.9, "campus": 1.0, "exam": 0.8, "schedule": 1.0, "credits": 1.0}
    if any(x in q for x in ["最重要", "优先", "第一优先"]):
        if "开卷" in q: priority["exam"] = 1.0
        if "玉泉路" in q: priority["campus"] = 1.0
        if any(x in q for x in ["AI", "agent", "智能体"]): priority["direction"] = 1.0
    return {
        "campus": campus, "exam_preference": exam, "min_core": min_core, "min_prof": min_prof, "min_public_elective": min_public_elective,
        "total_credits": total_credits, "avoid_days": avoid_days, "avoid_days_hard": avoid_days_hard,
        "keywords": " ".join(dict.fromkeys(keywords)), "priority": priority,
        "excluded_codes": [str(x) for x in defaults.get("excluded_codes", [])],
    }
