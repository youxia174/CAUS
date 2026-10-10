from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCHEDULE = BASE_DIR / "data" / "raw" / "course_plan_yjs.xlsx"

WANTED = [
    "课程编码", "课程名称", "开课院系", "开课校区", "课程属性", "培养层次",
    "所属学科/专业", "课时/学分", "开课周", "星期节次", "教室", "授课方式",
    "考试方式", "主讲教师", "首席教授"
]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated(keep="first")].copy()
    basic_cols = [
        "开课院系", "课程编码", "课程名称", "英文名称", "开课校区", "课程属性",
        "培养层次", "所属学科/专业", "课时/学分", "限选人数", "已选人数",
        "授课方式", "考试方式", "首席教授", "首席教授所属单位", "主讲教师", "主讲教师所属单位"
    ]
    fill_cols = [c for c in basic_cols if c in df.columns]
    if fill_cols:
        df[fill_cols] = df[fill_cols].ffill()
    return df


def load_schedule(path=DEFAULT_SCHEDULE) -> pd.DataFrame:
    """读取唯一课表；兼容多行课时记录和 Excel 合并单元格。"""
    sheets = pd.read_excel(path, sheet_name=None)
    frames = []
    for sheet_name, raw in sheets.items():
        raw = _clean(raw)
        for c in WANTED + ["开课周", "星期节次", "教室"]:
            if c not in raw.columns:
                raw[c] = ""
        selected_cols = list(dict.fromkeys(WANTED + ["开课周", "星期节次", "教室"]))
        df = raw[selected_cols].copy()
        df = df.loc[:, ~df.columns.duplicated(keep="first")].copy()
        for c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()
        df["来源工作表"] = str(sheet_name)
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=WANTED + ["开课周", "星期节次", "教室", "来源工作表"])

    df = pd.concat(frames, ignore_index=True)
    df = df[(df["课程编码"] != "") | (df["课程名称"] != "")].copy()
    # 课程编码是主键；极少数空编码课程退回课程名称。
    df["课程ID"] = df["课程编码"].where(df["课程编码"].str.strip() != "", df["课程名称"])
    df["schedule_text"] = df.apply(
        lambda r: f"开课周:{r['开课周']}；时间:{r['星期节次']}；教室:{r['教室']}", axis=1
    )
    return df.reset_index(drop=True)


def _first_nonempty(s):
    for x in s:
        if str(x).strip():
            return str(x).strip()
    return ""


def _join_unique(s):
    vals = []
    for x in s:
        x = str(x).strip()
        if x and x not in vals:
            vals.append(x)
    return "；".join(vals)


def parse_credits(value) -> float:
    text = str(value or "")
    import re
    m = re.search(r"/\s*(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else 0.0


def build_course_summary(schedule: pd.DataFrame) -> pd.DataFrame:
    if schedule.empty:
        return schedule.copy()
    agg = {
        "课程名称": _first_nonempty, "开课院系": _first_nonempty, "开课校区": _join_unique,
        "课程属性": _first_nonempty, "培养层次": _first_nonempty, "所属学科/专业": _first_nonempty,
        "课时/学分": _first_nonempty, "授课方式": _join_unique, "考试方式": _join_unique,
        "主讲教师": _join_unique, "首席教授": _join_unique, "开课周": _join_unique,
        "星期节次": _join_unique, "教室": _join_unique, "来源工作表": _join_unique,
    }
    out = schedule.groupby("课程ID", as_index=False).agg(agg)
    out["课程编码"] = out["课程ID"]
    out["学分"] = out["课时/学分"].map(parse_credits)
    out["课程文本"] = out.apply(
        lambda r: " | ".join(str(r.get(c, "")) for c in [
            "课程名称", "开课院系", "课程属性", "所属学科/专业", "授课方式", "考试方式", "主讲教师"
        ]), axis=1
    )
    return out
