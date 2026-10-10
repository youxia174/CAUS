import streamlit as st
import pandas as pd
from agent.data_loader import load_schedule, build_course_summary
from agent.tools import CourseTools
from agent.course_agent import CourseAgent
from agent.parser import parse_request
from agent.state import init_state, add_message
from agent.exporter import export_plan
from rag.retriever import CourseRetriever
from solver.schedule_solver import detect_conflicts

st.set_page_config(page_title="GradCourse-Agent", page_icon="🎓", layout="wide")
init_state()

@st.cache_data(show_spinner="正在加载课表…")
def load_data():
    schedule = load_schedule()
    summary = build_course_summary(schedule)
    return schedule, summary

schedule, summary = load_data()

@st.cache_resource(show_spinner="正在建立课程检索与冲突索引…")
def build_runtime(summary, schedule):
    retriever = CourseRetriever(summary)
    tools = CourseTools(schedule, summary, retriever)
    agent = CourseAgent(tools, retriever)
    return retriever, tools, agent

retriever, tools, agent = build_runtime(summary, schedule)

st.title("🎓 GradCourse-Agent")
st.caption("LLM Agent + Tool Calling + 约束优化 + 课程检索 + 多轮调整")

with st.sidebar:
    st.header("选课约束")
    campus = st.selectbox("校区", ["玉泉路", "不限", "雁栖湖", "中关村"], index=0)
    exam_preference = st.selectbox("考试方式", ["只选开卷", "开卷优先", "不限"], index=0)
    min_core = st.number_input("核心课至少", 0, 10, 2)
    min_prof = st.number_input("专业课至少", 0, 10, 2)
    min_public_elective = st.number_input("公共选修课至少", 0, 10, 0)
    total_credits = st.number_input("总学分目标（0=不限制）", 0.0, 30.0, 0.0, step=0.5)
    avoid_days = st.multiselect("尽量避免上课的星期", ["周一","周二","周三","周四","周五","周六","周日"])
    st.divider()
    st.metric("课程数量", len(summary))
    st.metric("教学安排记录", len(schedule))
    st.caption("硬约束：校区、核心/专业课数量、时间冲突。软约束：方向、开卷偏好、避免某天。")

# 需求输入
query = st.text_area(
    "告诉 Agent 你的需求",
    "我是电子信息研一，想往 AI Agent 方向发展；优先玉泉路，全部开卷，核心课至少2门、专业课至少2门，不要周五，尽量避免时间冲突。",
    height=120,
)

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🚀 开始智能规划", type="primary", use_container_width=True):
        defaults = {"campus": campus, "exam_preference": exam_preference, "min_core": min_core,
                    "min_prof": min_prof, "min_public_elective": min_public_elective, "total_credits": total_credits, "avoid_days": avoid_days,
                    "excluded_codes": st.session_state.excluded_codes,
                    "current_courses": ([{"name": str(r["课程名称"]), "code": str(r["课程ID"])} for _, r in st.session_state.plan["courses"].iterrows()] if st.session_state.plan else [])}
        status = st.status("Agent 正在规划…", expanded=True)
        try:
            status.write("① 解析用户需求与约束")
            result = agent.answer(query, defaults)
            st.session_state.plan = result
            st.session_state.trace = result["trace"]
            add_message("user", query)
            add_message("assistant", result["text"])
            status.write("② Agent 调用课程检索/优化工具")
            status.write("③ 检查周次 + 星期 + 节次冲突")
            status.write("④ 如无解，自动调整软约束并重新规划")
            status.update(label="智能规划完成", state="complete", expanded=False)
        except Exception as e:
            status.update(label="规划失败", state="error", expanded=True)
            st.exception(e)

with col2:
    if st.button("🧹 清空当前方案", use_container_width=True):
        st.session_state.plan = None
        st.session_state.trace = []
        st.session_state.messages = []
        st.session_state.excluded_codes = []
        st.rerun()

plan = st.session_state.plan
if plan:
    courses = plan["courses"].copy()
    meta = plan["meta"]
    constraints = plan["constraints"]

    st.success("方案已生成")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("总学分", f"{meta.get('credits', 0):.1f}")
    m2.metric("核心课", meta.get("core_count", 0))
    m3.metric("专业课", meta.get("professional_count", 0))
    conflicts = tools.check_conflict(courses["课程ID"].tolist()) if not courses.empty else []
    m4.metric("时间冲突", len(conflicts))

    tab1, tab2, tab3, tab4 = st.tabs(["📚 推荐方案", "🗓️ 课表视图", "🤖 Agent轨迹", "💬 多轮调整"])

    with tab1:
        if not courses.empty:
            display_cols = [c for c in ["课程名称","课程编码","开课校区","课程属性","学分","考试方式","星期节次","开课周","教室","主讲教师"] if c in courses.columns]
            st.dataframe(courses[display_cols], use_container_width=True, hide_index=True)
            st.download_button("📥 导出 Excel", data=export_plan(courses, tools.get_schedule(courses["课程ID"].tolist())), file_name="GradCourse-Agent-选课方案.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.subheader("手动调整")
            options = {f"{r['课程名称']}（{r['课程编码']}）": r['课程ID'] for _, r in courses.iterrows()}
            if options:
                remove_label = st.selectbox("删除一门并自动重新规划", list(options))
                if st.button("删除并重新规划"):
                    code = options[remove_label]
                    st.session_state.excluded_codes.append(str(code))
                    defaults = {"campus": campus, "exam_preference": exam_preference, "min_core": min_core,
                                "min_prof": min_prof, "min_public_elective": min_public_elective, "total_credits": total_credits, "avoid_days": avoid_days,
                    "excluded_codes": st.session_state.excluded_codes,
                    "current_courses": ([{"name": str(r["课程名称"]), "code": str(r["课程ID"])} for _, r in st.session_state.plan["courses"].iterrows()] if st.session_state.plan else [])}
                    q2 = query + f"；不要选择课程：{remove_label}"
                    result = agent.answer(q2, defaults)
                    st.session_state.plan = result
                    st.session_state.trace = result["trace"]
                    st.rerun()
        else:
            st.warning("当前约束下没有可行方案。建议把“只选开卷”改成“开卷优先”，或减少最低课程数量。")

        if meta.get("warnings"):
            st.subheader("约束诊断")
            for w in meta["warnings"]:
                st.warning(w)

    with tab2:
        st.caption("按真实周次 + 星期 + 节次生成简化课表。不同周次不视为冲突。")
        rows = []
        for _, r in courses.iterrows():
            rows.append({"课程": r["课程名称"], "周次": r.get("开课周", ""), "星期节次": r.get("星期节次", ""), "教室": r.get("教室", "")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if conflicts:
            st.error("发现冲突")
            st.dataframe(pd.DataFrame(conflicts), use_container_width=True, hide_index=True)
        else:
            st.success("当前方案没有检测到时间冲突。")

    with tab3:
        st.caption("这里展示 Agent 的规划/工具调用轨迹，方便调试和面试演示。")
        for item in st.session_state.trace:
            st.write(f"**Step {item.get('step')} · {item.get('action')}**")
            if item.get("result"): st.caption(item["result"])
            if item.get("args"): st.json(item["args"])

    with tab4:
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        new_query = st.chat_input("例如：删掉机器学习，换一门更轻松的AI课程")
        if new_query:
            defaults = {"campus": campus, "exam_preference": exam_preference, "min_core": min_core,
                        "min_prof": min_prof, "min_public_elective": min_public_elective, "total_credits": total_credits, "avoid_days": avoid_days,
                    "excluded_codes": st.session_state.excluded_codes,
                    "current_courses": ([{"name": str(r["课程名称"]), "code": str(r["课程ID"])} for _, r in st.session_state.plan["courses"].iterrows()] if st.session_state.plan else [])}
            result = agent.answer(new_query, defaults)
            st.session_state.plan = result
            st.session_state.trace = result["trace"]
            add_message("user", new_query)
            add_message("assistant", result["text"])
            st.rerun()

st.divider()
search_tab, data_tab = st.tabs(["🔎 课程检索", "📋 原始课表"])
with search_tab:
    q = st.text_input("语义检索课程", "大模型 Agent")
    if q:
        st.dataframe(retriever.search(q, 15), use_container_width=True, hide_index=True)
with data_tab:
    cols = ["课程编码","课程名称","开课院系","开课校区","课程属性","课时/学分","开课周","星期节次","教室","授课方式","考试方式","主讲教师"]
    st.dataframe(schedule[cols], use_container_width=True, hide_index=True)
