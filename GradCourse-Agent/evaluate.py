from pathlib import Path
import json
from agent.parser import parse_request

CASES = [
    {"query": "AI Agent方向，玉泉路，全部开卷，核心课至少2门，专业课至少2门", "campus": "玉泉路", "exam": "只选开卷", "min_core": 2, "min_prof": 2},
    {"query": "我想做大模型，玉泉路，开卷优先，不要周五", "campus": "玉泉路", "exam": "开卷优先"},
    {"query": "机器学习方向，总学分至少8学分", "credits": 8},
]


def run_evaluation():
    rows = []
    for case in CASES:
        p = parse_request(case["query"])
        rows.append({
            "query": case["query"],
            "campus_ok": p["campus"] == case.get("campus", p["campus"]),
            "exam_ok": p["exam_preference"] == case.get("exam", p["exam_preference"]),
            "core_ok": p["min_core"] == case.get("min_core", p["min_core"]),
            "prof_ok": p["min_prof"] == case.get("min_prof", p["min_prof"]),
            "credits_ok": p["total_credits"] == case.get("credits", p["total_credits"]),
        })
    return rows


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), ensure_ascii=False, indent=2))
