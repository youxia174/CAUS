# GradCourse-Agent V3

研究生个性化智能选课 Agent：单课表数据源 + LLM Tool Calling + 约束优化 + 周次冲突检测 + 多轮调整 + FastAPI + Streamlit + Evaluation。

## 1. 核心能力
- 单 Excel 数据源：`data/raw/course_plan_yjs.xlsx`
- 课程编码/课程ID作为唯一键
- Excel 合并单元格自动向下填充
- 课程摘要与多条教学安排分离
- LLM 负责自然语言理解、规划和解释
- Python Tool 负责课程搜索、课表查询、冲突检测、课程优化
- 时间冲突按 `周次 + 星期 + 节次` 判断
- Hard Constraints：校区、核心/专业课最低数量、时间不冲突
- Soft Constraints：方向匹配、开卷偏好、避免某天
- 无解时自动尝试放宽“只选开卷”到“开卷优先”，但不放宽学位课数量和时间冲突
- 支持多轮聊天、手动删除课程后重新规划
- 支持 Excel 导出
- 支持 Agent Trace
- FastAPI API
- pytest 基础测试
- 本地 TF-IDF 检索作为零下载依赖的 RAG/检索层

## 2. 为什么没有强制使用 Chroma
当前项目优先保证 Windows/新手环境一键运行。课程数据量只有约两千门，用本地 TF-IDF 已足够快速。项目额外提供 `rag/chroma_retriever.py`，需要时可 `pip install -r requirements-optional.txt` 使用本地 Chroma；默认 TF-IDF 版本不下载 embedding 模型，保证新手环境更稳定。

## 3. 安装
```bash
pip install -r requirements.txt
```

## 4. 配置 LLM
复制 `.env.example` 为 `.env`，填写：
```text
LLM_API_KEY=...
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=...
```
如果没有配置 LLM，系统仍可使用本地规则优化和 fallback。

## 5. 运行网页
```bash
streamlit run app.py
```

## 6. 运行 API
```bash
uvicorn api:app --reload
```
健康检查：`GET /health`
推荐接口：`POST /api/course/recommend`

## 7. 测试
```bash
pytest -q
```

## 8. 项目结构
```text
GradCourse-Agent/
├── app.py
├── api.py
├── evaluate.py
├── agent/
│   ├── course_agent.py   # Agent循环、Tool Calling、fallback
│   ├── parser.py         # 需求解析
│   ├── tools.py          # Agent工具
│   ├── data_loader.py    # Excel清洗与课程聚合
│   ├── llm.py            # LLM API层
│   ├── exporter.py       # Excel导出
│   └── state.py           # Streamlit会话状态
├── rag/retriever.py       # 本地课程检索
├── solver/schedule_solver.py # 约束优化与时间冲突
├── tests/
└── data/raw/course_plan_yjs.xlsx
```

## 9. 面试时怎么讲
不要说“LLM帮我选课”。应该说：
1. LLM把自然语言转成结构化约束。
2. Agent根据任务调用 CourseSearch / Schedule / Conflict / Optimizer 工具。
3. 硬约束由确定性代码保证，避免LLM幻觉。
4. 软约束通过评分函数进行多目标优化。
5. 发现冲突/无解后，Agent重新调用工具进行 re-planning。
6. 最后由LLM解释可执行方案。

## 10. 当前版本的边界
- 没有接入飞书课程评价数据：当前数据源只有学校课表 Excel。
- 默认不强制下载外部 embedding 模型；RAG 层使用本地 TF-IDF，保证首次运行稳定。
- `rag/chroma_retriever.py` 是可选升级路径，不影响默认版本。
- Tool Calling 是否实际执行取决于你配置的 LLM endpoint 是否支持 OpenAI-compatible function calling；不支持时系统会自动走确定性 fallback。
