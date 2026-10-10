import re
import itertools
import pandas as pd

DAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}


def parse_periods(text):
    text = str(text or "")
    result = []
    patterns = [
        r"(?:星期|周)([一二三四五六日天])\s*[（(]?\s*(\d+)\s*[-~－—]\s*(\d+)\s*[）)]?",
        r"(?:星期|周)([一二三四五六日天])\s*[（(]?\s*(\d+)(?:、|,|，)\s*(\d+)\s*[）)]?",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            day = DAY_MAP[m.group(1)]
            a, b = int(m.group(2)), int(m.group(3))
            if a > b:
                a, b = b, a
            result.extend((day, p) for p in range(a, b + 1))
    # 去重保持顺序
    return list(dict.fromkeys(result))


def parse_weeks(text):
    """支持 第2-5,7-18周 / 第2至5周 / 第2,4,6周 / 第2-18周。"""
    text = str(text or "")
    if not text.strip():
        return set(range(1, 21))
    normalized = text.replace("，", ",").replace("－", "-").replace("—", "-").replace("~", "-").replace("至", "-")
    weeks = set()
    for m in re.finditer(r"第\s*([0-9,\-\s]+)\s*周", normalized):
        body = re.sub(r"\s+", "", m.group(1))
        for item in body.split(","):
            if not item:
                continue
            if "-" in item:
                a, b = item.split("-", 1)
                try:
                    a, b = int(a), int(b)
                    weeks.update(range(min(a, b), max(a, b) + 1))
                except ValueError:
                    pass
            else:
                try:
                    weeks.add(int(item))
                except ValueError:
                    pass
    return weeks or set(range(1, 21))


def row_slots(row):
    weeks = parse_weeks(row.get("开课周", ""))
    periods = parse_periods(row.get("星期节次", ""))
    return {(w, d, p) for w in weeks for d, p in periods}


def detect_conflicts(selected_rows: pd.DataFrame):
    occupied = {}
    conflicts = []
    seen_pairs = set()
    for _, row in selected_rows.iterrows():
        name = str(row.get("课程名称", ""))
        code = str(row.get("课程ID", row.get("课程编码", "")))
        for slot in row_slots(row):
            if slot in occupied:
                old_name, old_code = occupied[slot]
                if old_code != code:
                    pair = tuple(sorted([old_code, code]))
                    key = (pair, slot)
                    if key not in seen_pairs:
                        seen_pairs.add(key)
                        conflicts.append({
                            "课程1": old_name,
                            "课程2": name,
                            "周": slot[0], "星期": slot[1], "节次": slot[2],
                            "时间": f"第{slot[0]}周 周{slot[1]} 第{slot[2]}节",
                        })
            else:
                occupied[slot] = (name, code)
    return conflicts


def build_conflict_map(schedule: pd.DataFrame):
    """预计算课程编码之间的冲突关系，优化大量组合搜索的速度。"""
    slot_to_codes = {}
    for _, row in schedule.iterrows():
        code = str(row.get("课程ID", row.get("课程编码", "")))
        if not code: continue
        for slot in row_slots(row):
            slot_to_codes.setdefault(slot, set()).add(code)
    conflict_map = {}
    for codes in slot_to_codes.values():
        codes = list(codes)
        for a in codes:
            conflict_map.setdefault(a, set()).update(x for x in codes if x != a)
    return conflict_map


def has_conflict(schedule: pd.DataFrame, selected_codes):
    codes = {str(x) for x in selected_codes}
    rows = schedule[schedule["课程ID"].astype(str).isin(codes)]
    return len(detect_conflicts(rows)) > 0


def _is_core(attr):
    return "核心" in str(attr)


def _is_prof(attr):
    # “专业核心课”按核心课统计；只有普通“专业课”计入专业课配额。
    text = str(attr)
    return "专业" in text and "核心" not in text


def _is_open(exam):
    return "开卷" in str(exam)


def _direction_score(row, keywords):
    name = str(row.get("课程名称", ""))
    field = str(row.get("所属学科/专业", ""))
    text = (name + " " + field).lower()
    keys = [k.strip().lower() for k in re.split(r"[,，\s]+", str(keywords)) if k.strip()]
    score = 0.0
    # 面向 AI/Agent 的领域词：强匹配优先于字符相似，避免“自然语言”把“语言学”误判为 NLP。
    ai_terms = [
        "人工智能", "机器学习", "深度学习", "大模型", "智能体", "agent", "自然语言处理",
        "算法", "软件工程", "知识工程", "强化学习", "计算机视觉", "模式识别", "数据挖掘",
        "智能决策", "智能软件", "图像处理", "计算机", "gpu", "神经网络", "推荐系统",
        "信息论", "信号处理", "统计", "概率", "优化", "数字图像", "数字信号", "数学"
    ]
    negative_terms = ["语言学", "文艺批评", "人力资源", "环境化学", "化学", "管理学", "财务", "水化学", "声学", "半导体工艺"]
    for term in ai_terms:
        if term in text:
            score += 35 if term in name.lower() else 12
    for term in negative_terms:
        if term in name.lower():
            score -= 30
    for k in keys:
        if k and k in name.lower():
            score += 20
        elif k and k in field.lower():
            score += 8
    return score


def candidate_score(row, keywords, exam_preference="", campus="", avoid_days=None, priority=None):
    priority = priority or {}
    direction_w = float(priority.get("direction", 0.9))
    exam_w = float(priority.get("exam", 0.8))
    schedule_w = float(priority.get("schedule", 1.0))
    score = _direction_score(row, keywords) * direction_w
    score += float(row.get("_检索相关度", 0.0) or 0.0) * 80.0 * direction_w
    if exam_preference == "只选开卷" and _is_open(row.get("考试方式", "")): score += 20 * exam_w
    if exam_preference == "开卷优先": score += 20 * exam_w if _is_open(row.get("考试方式", "")) else 0
    if campus and campus != "不限" and campus in str(row.get("开课校区", "")): score += 10
    if avoid_days:
        day_text = str(row.get("星期节次", ""))
        score -= sum(5 * schedule_w for d in avoid_days if d in day_text)
    return score


def optimize_courses(summary, schedule, keywords="", campus="不限", exam_preference="不限",
                      min_core=2, min_prof=2, min_public_elective=0, total_credits=0, avoid_days=None, avoid_days_hard=False,
                      excluded_codes=None, preferred_codes=None, priority=None, conflict_map=None):
    """硬约束+软约束贪心优化。无解时逐级放宽软约束，不放宽学位课数量和时间冲突。"""
    data = summary.copy()
    excluded = {str(x) for x in (excluded_codes or [])}
    preferred = {str(x) for x in (preferred_codes or [])}
    for c in ["开课校区", "考试方式", "课程属性", "课程名称", "所属学科/专业", "培养层次"]:
        if c not in data.columns: data[c] = ""
        data[c] = data[c].fillna("").astype(str).str.strip()
    warnings = []

    # Hard filters：默认面向全日制硕士，排除明确标记的非全日制/纯博士课程。
    level = data["培养层次"].astype(str)
    data = data[~level.str.contains("非全日制", regex=False, na=False)].copy()
    data = data[~data["课程名称"].astype(str).str.contains("非全日制", regex=False, na=False)].copy()
    if campus and campus != "不限":
        data = data[data["开课校区"].str.contains(campus, regex=False, na=False)].copy()
    if exam_preference == "只选开卷":
        data = data[data["考试方式"].map(_is_open)].copy()
    if excluded:
        data = data[~data["课程ID"].astype(str).isin(excluded)].copy()
    if avoid_days and avoid_days_hard:
        # 明确说“不要周X”时作为硬约束：只要该课程存在目标星期的教学安排，就排除。
        bad_ids = set()
        for _, rr in schedule.iterrows():
            if any(d in str(rr.get("星期节次", "")) for d in avoid_days):
                bad_ids.add(str(rr.get("课程ID", "")))
        data = data[~data["课程ID"].astype(str).isin(bad_ids)].copy()

    if data.empty:
        warnings.append("硬约束过滤后没有候选课程")
        return data, {"warnings": warnings, "hard_constraints_satisfied": False, "score": 0}

    data["方向分"] = data.apply(lambda r: candidate_score(r, keywords, exam_preference, campus, avoid_days, priority), axis=1)
    data["优先分"] = data["方向分"] + data["课程ID"].astype(str).map(lambda x: 100 if x in preferred else 0)

    schedule = schedule.copy()
    schedule["课程ID"] = schedule["课程ID"].astype(str)
    conflict_map = conflict_map if conflict_map is not None else build_conflict_map(schedule)
    # 全局小规模组合搜索：先取每类最高分候选，比较“课程方向分 + 开卷偏好 + 避免星期”
    # 的组合总分，而不是按课程逐门贪心，减少“选了A导致B无法加入”的局部最优问题。
    selected = []
    selected_ids = []

    def combo_ok(ids):
        ids = [str(x) for x in ids]
        chosen = set(ids)
        for code in ids:
            if conflict_map.get(code, set()) & (chosen - {code}):
                return False
        return True

    def combo_score(rows):
        return float(rows["优先分"].sum())

    core_cap = 12 if int(min_core) <= 2 else 8
    prof_cap = 16 if int(min_prof) <= 2 else 10
    public_cap = 6 if int(min_public_elective) <= 1 else 5
    core = data[data["课程属性"].map(_is_core)].sort_values("优先分", ascending=False).head(core_cap)
    prof = data[data["课程属性"].map(_is_prof)].sort_values("优先分", ascending=False).head(prof_cap)
    public = data[data["课程属性"].str.contains("公共选修", regex=False, na=False)].sort_values("优先分", ascending=False).head(public_cap)
    core_n, prof_n, public_n = int(min_core), int(min_prof), int(min_public_elective)
    best_ids, best_score = None, float("-inf")

    # 控制组合数量；常用的2+2场景可以穷举，较大配额采用前N候选回溯。
    core_combos = itertools.combinations(core["课程ID"].astype(str).tolist(), core_n) if core_n <= 4 else []
    core_combos = list(core_combos)[:5000] if core_n <= 4 else []
    if core_n > 4:
        core_combos = [tuple(core["课程ID"].astype(str).head(core_n).tolist())]
    prof_ids = prof["课程ID"].astype(str).tolist()
    prof_combos = list(itertools.combinations(prof_ids, prof_n))[:5000] if prof_n <= 4 else [tuple(prof_ids[:prof_n])]
    pub_ids = public["课程ID"].astype(str).tolist()
    pub_combos = list(itertools.combinations(pub_ids, public_n))[:1000] if public_n <= 2 else [tuple(pub_ids[:public_n])]
    if public_n == 0: pub_combos = [tuple()]

    for cc in core_combos:
        if not combo_ok(cc): continue
        for pc in prof_combos:
            base = list(cc) + [x for x in pc if x not in cc]
            if len(base) < core_n + prof_n: continue
            for uc in pub_combos:
                ids = base + [x for x in uc if x not in base]
                if len(ids) < core_n + prof_n + public_n: continue
                if combo_ok(ids):
                    rows = data[data["课程ID"].astype(str).isin(ids)]
                    sc = combo_score(rows)
                    credits = float(rows["学分"].sum()) if "学分" in rows else 0.0
                    sc += min(credits, float(total_credits or 0)) * 0.1
                    if sc > best_score:
                        best_score, best_ids = sc, ids

    if best_ids is None:
        warnings.append("没有找到同时满足核心/专业课数量和时间不冲突的组合")
    else:
        selected_ids = list(dict.fromkeys(best_ids))
        selected = [data[data["课程ID"].astype(str) == code].iloc[0] for code in selected_ids]

    # 如果有总学分目标，再从剩余候选中继续加入不冲突课程。
    current_credits = sum(float(x.get("学分", 0) or 0) for x in selected)
    if total_credits and current_credits < float(total_credits):
        for _, r in data.sort_values("优先分", ascending=False).iterrows():
            if current_credits >= float(total_credits): break
            code = str(r["课程ID"])
            if code in selected_ids: continue
            if combo_ok(selected_ids + [code]):
                selected.append(r); selected_ids.append(code)
                current_credits += float(r.get("学分", 0) or 0)

    result = pd.DataFrame(selected)
    if result.empty:
        result = data.head(0).copy()
    final_score = float(result["优先分"].sum()) if "优先分" in result else 0.0
    result = result.drop(columns=["方向分", "优先分", "_检索相关度", "检索相关度"], errors="ignore")
    final_conflicts = detect_conflicts(schedule[schedule["课程ID"].isin(selected_ids)])
    core_n = int(result["课程属性"].map(_is_core).sum()) if not result.empty else 0
    prof_n_actual = int(result["课程属性"].map(_is_prof).sum()) if not result.empty else 0
    public_n_actual = int(result["课程属性"].str.contains("公共选修", regex=False, na=False).sum()) if not result.empty else 0
    credits_value = float(result["学分"].sum()) if not result.empty else 0.0
    credit_ok = (not total_credits) or credits_value >= float(total_credits)
    public_ok = public_n_actual >= int(min_public_elective)
    hard_ok = core_n >= int(min_core) and prof_n_actual >= int(min_prof) and public_ok and credit_ok and not final_conflicts
    if total_credits and not credit_ok:
        warnings.append(f"总学分目标未完全满足：当前 {credits_value:.1f} / 目标 {float(total_credits):.1f} 学分")
    return result, {
        "warnings": warnings,
        "hard_constraints_satisfied": hard_ok,
        "core_count": core_n,
        "professional_count": prof_n_actual,
        "public_elective_count": public_n_actual,
        "credits": credits_value,
        "credit_target": float(total_credits),
        "public_elective_target": int(min_public_elective),
        "score": final_score,
        "selected_codes": selected_ids,
    }
