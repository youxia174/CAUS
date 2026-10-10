from agent.parser import parse_request


def test_parse_constraints():
    p = parse_request("AI Agent方向，玉泉路，全部开卷，核心课至少2门，专业课至少2门，不要周五")
    assert p["campus"] == "玉泉路"
    assert p["exam_preference"] == "只选开卷"
    assert p["min_core"] == 2
    assert p["min_prof"] == 2
    assert "周五" in p["avoid_days"]
