import pandas as pd
from solver.schedule_solver import detect_conflicts, optimize_courses, build_conflict_map


class CourseTools:
    def __init__(self, schedule, summary, retriever=None):
        self.schedule = schedule
        self.summary = summary
        self.retriever = retriever
        self.conflict_map = build_conflict_map(schedule)

    def search_courses(self, query="", campus="不限", top_k=20):
        data = self.summary.copy()
        if campus and campus != "不限":
            data = data[data["开课校区"].astype(str).str.contains(campus, regex=False, na=False)]
        if self.retriever and query:
            result = self.retriever.search(query, top_k=top_k)
            if campus and campus != "不限":
                result = result[result["开课校区"].astype(str).str.contains(campus, regex=False, na=False)]
            return result.head(top_k)
        return data.head(top_k)

    def get_schedule(self, course_codes=None):
        if not course_codes:
            return self.schedule.head(100).copy()
        codes = {str(x) for x in course_codes}
        return self.schedule[self.schedule["课程ID"].astype(str).isin(codes)].copy()

    def check_conflict(self, course_codes):
        return detect_conflicts(self.get_schedule(course_codes))

    def optimize(self, keywords="", campus="不限", exam_preference="不限", min_core=2,
                 min_prof=2, min_public_elective=0, total_credits=0, avoid_days=None, avoid_days_hard=False, excluded_codes=None,
                 preferred_codes=None, priority=None):
        data = self.summary.copy()
        # 用检索层给方向匹配提供连续分数，再交给确定性优化器做硬约束。
        if self.retriever is not None and keywords:
            try:
                hit = self.retriever.search(keywords, top_k=len(data))[["课程ID", "检索相关度"]]
                data = data.merge(hit, on="课程ID", how="left")
                data["_检索相关度"] = data["检索相关度"].fillna(0.0)
            except Exception:
                data["_检索相关度"] = 0.0
        else:
            data["_检索相关度"] = 0.0
        return optimize_courses(
            data, self.schedule, keywords, campus, exam_preference,
            min_core, min_prof, min_public_elective, total_credits, avoid_days, avoid_days_hard, excluded_codes, preferred_codes, priority, self.conflict_map
        )

    def replace_course(self, selected_codes, remove_code, keywords="", **constraints):
        selected = [str(x) for x in selected_codes if str(x) != str(remove_code)]
        result, meta = self.optimize(keywords=keywords, excluded_codes=set(), preferred_codes=selected, **constraints)
        return result, meta
