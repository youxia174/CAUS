import pandas as pd
from solver.schedule_solver import parse_weeks, parse_periods, detect_conflicts


def test_parse_weeks():
    assert parse_weeks("第2-5,7-9周") == {2,3,4,5,7,8,9}


def test_parse_periods():
    assert (2,5) in parse_periods("周二(5-6)")
    assert (2,6) in parse_periods("周二(5-6)")


def test_different_weeks_not_conflict():
    df = pd.DataFrame([
        {"课程ID":"A","课程名称":"A","开课周":"第1-8周","星期节次":"周二(5-6)"},
        {"课程ID":"B","课程名称":"B","开课周":"第9-16周","星期节次":"周二(5-6)"},
    ])
    assert detect_conflicts(df) == []


def test_overlapping_week_conflict():
    df = pd.DataFrame([
        {"课程ID":"A","课程名称":"A","开课周":"第1-8周","星期节次":"周二(5-6)"},
        {"课程ID":"B","课程名称":"B","开课周":"第5-12周","星期节次":"周二(6-7)"},
    ])
    assert detect_conflicts(df)
