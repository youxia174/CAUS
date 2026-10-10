from fastapi import FastAPI
from pydantic import BaseModel, Field
from agent.data_loader import load_schedule, build_course_summary
from agent.tools import CourseTools
from agent.course_agent import CourseAgent
from rag.retriever import CourseRetriever

app = FastAPI(title="GradCourse-Agent API", version="3.0")
schedule = load_schedule()
summary = build_course_summary(schedule)
retriever = CourseRetriever(summary)
tools = CourseTools(schedule, summary, retriever)
agent = CourseAgent(tools, retriever)

class RecommendRequest(BaseModel):
    query: str
    campus: str = "不限"
    exam_preference: str = "不限"
    min_core: int = Field(2, ge=0, le=10)
    min_prof: int = Field(2, ge=0, le=10)
    total_credits: float = Field(0, ge=0, le=30)
    avoid_days: list[str] = []

@app.get("/health")
def health():
    return {"status": "ok", "courses": len(summary), "schedule_records": len(schedule)}

@app.post("/api/course/recommend")
def recommend(req: RecommendRequest):
    result = agent.answer(req.query, req.model_dump())
    return {
        "answer": result["text"],
        "constraints": result["constraints"],
        "meta": result["meta"],
        "courses": result["courses"].to_dict("records"),
        "trace": result["trace"],
    }
