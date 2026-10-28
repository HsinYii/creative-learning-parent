from fastapi import FastAPI

from . import intercept_log
from .pipeline import handle
from .schemas import ChatRequest, ChatResponse

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    resp = handle(req.session_id, req.message)
    if resp.guardrail.triggered:
        intercept_log.record(req.session_id, req.message, resp.guardrail)
    return resp


@app.get("/interceptions")
def interceptions() -> list[dict]:
    """攔截紀錄，新的在前。"""
    return intercept_log.read_all()[::-1]
