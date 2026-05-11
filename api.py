import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from core.models import RequirementsModel, BotFlowModel
from core.pipeline import _load_config, _make_llm
from core import settings_store
import agents.agent1_interviewer as agent1
import agents.agent2_flow_builder as agent2
import agents.agent3_exporter as agent3

app = FastAPI(
    title="Studio System API",
    description="AI-powered WhatsApp Bot Generator Pipeline",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    session_id: str
    answers: dict = field(default_factory=dict)
    next_question_index: int = 0
    status: Literal["interviewing", "compiled", "building", "done", "error"] = "interviewing"
    requirements: dict | None = None
    output_folder: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    # Answer-validation state
    follow_up_count: int = 0
    is_follow_up: bool = False
    follow_up_question: str | None = None


sessions: dict[str, SessionState] = {}
QUESTIONS = agent1.get_questions()


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------

class SettingsUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    model: str = "gpt-4o"


@app.get("/settings")
async def get_settings():
    s = settings_store.load()
    key = s.get("openai_api_key", "")
    return {
        "configured": bool(key),
        "openai_api_key_preview": f"sk-...{key[-4:]}" if len(key) > 8 else ("(set)" if key else ""),
        "model": s.get("model", "gpt-4o"),
    }


@app.post("/settings")
async def update_settings(body: SettingsUpdate):
    s = settings_store.load()
    if body.openai_api_key and body.openai_api_key.strip():
        s["openai_api_key"] = body.openai_api_key.strip()
    s["model"] = body.model
    settings_store.save(s)
    return {"status": "saved"}


# ---------------------------------------------------------------------------
# Interview session endpoints
# ---------------------------------------------------------------------------

@app.post("/session/start")
async def start_session():
    """Create a new interview session and return the first question."""
    sid = str(uuid4())
    sessions[sid] = SessionState(session_id=sid)
    q = QUESTIONS[0]
    return {
        "session_id": sid,
        "question_index": 0,
        "question_field": q[0],
        "question_text": q[1],
        "total_questions": len(QUESTIONS),
    }


class AnswerRequest(BaseModel):
    answer: str


@app.post("/session/{session_id}/answer")
async def submit_answer(session_id: str, body: AnswerRequest):
    """Submit an answer (or follow-up) to the current question.

    Response status values:
    - "follow_up"    — answer was insufficient; a guiding question is returned.
    - "interviewing" — answer accepted; next question is returned.
    - "compiled"     — all answers collected; compiled requirements are returned.
    """
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "interviewing":
        raise HTTPException(status_code=409, detail=f"Session is in state '{session.status}', expected 'interviewing'")

    idx = session.next_question_index
    field_name, question_text = QUESTIONS[idx]
    incoming = body.answer.strip()

    if session.is_follow_up and session.answers.get(field_name):
        accumulated = session.answers[field_name] + "\n" + incoming if incoming else session.answers[field_name]
    else:
        accumulated = incoming
    session.answers[field_name] = accumulated

    config = _load_config()
    llm = _make_llm(config)

    if session.follow_up_count < agent1.MAX_FOLLOW_UPS:
        validation = await asyncio.to_thread(
            agent1.validate_answer, field_name, question_text, accumulated, llm
        )
        if not validation["valid"]:
            session.follow_up_count += 1
            session.is_follow_up = True
            follow_up_q = validation.get("follow_up") or f"Could you elaborate on: {question_text}"
            session.follow_up_question = follow_up_q
            return {
                "status": "follow_up",
                "question_index": idx,
                "question_field": field_name,
                "follow_up_question": follow_up_q,
                "follow_up_attempt": session.follow_up_count,
                "max_follow_ups": agent1.MAX_FOLLOW_UPS,
                "total_questions": len(QUESTIONS),
            }

    session.follow_up_count = 0
    session.is_follow_up = False
    session.follow_up_question = None
    session.next_question_index = idx + 1

    if session.next_question_index < len(QUESTIONS):
        q = QUESTIONS[session.next_question_index]
        return {
            "status": "interviewing",
            "question_index": session.next_question_index,
            "question_field": q[0],
            "question_text": q[1],
            "total_questions": len(QUESTIONS),
        }

    try:
        requirements = await asyncio.to_thread(
            agent1.compile_requirements, session.answers, llm
        )
    except Exception as e:
        session.status = "error"
        session.error = str(e)
        raise HTTPException(status_code=422, detail=f"Failed to compile requirements: {e}")

    session.requirements = requirements.model_dump()
    session.status = "compiled"

    return {
        "status": "compiled",
        "requirements": session.requirements,
    }


# ---------------------------------------------------------------------------
# Generation (SSE)
# ---------------------------------------------------------------------------

@app.post("/session/{session_id}/confirm")
async def confirm_and_build(session_id: str):
    """Confirm requirements and stream generation progress as SSE events."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "compiled":
        raise HTTPException(
            status_code=409,
            detail=f"Session is in state '{session.status}', expected 'compiled'",
        )

    session.status = "building"
    requirements = RequirementsModel(**session.requirements)

    async def event_stream():
        yield _sse("progress", {"step": 1, "total": 3, "message": "Requirements confirmed. Starting bot generation..."})
        await asyncio.sleep(0.1)

        config = _load_config()
        llm = _make_llm(config)
        max_retries = config.get("agent2", {}).get("max_retries", 2)
        output_dir = config.get("output_dir", "./output")

        yield _sse("progress", {"step": 2, "total": 3, "message": "Agent 2 is designing the bot flow (20-40 sec)..."})

        try:
            bot_flow: BotFlowModel = await asyncio.to_thread(
                lambda: agent2.run(requirements, llm, max_retries=max_retries)
            )
        except Exception as e:
            session.status = "error"
            session.error = str(e)
            yield _sse("error", {"message": str(e)})
            return

        yield _sse("progress", {
            "step": 2,
            "total": 3,
            "message": f"Bot flow ready: {bot_flow.name} ({len(bot_flow.intents)} blocks)",
            "done": True,
        })

        yield _sse("progress", {"step": 3, "total": 3, "message": "Exporting files..."})

        try:
            out_path: Path = await asyncio.to_thread(
                lambda: agent3.run(requirements, bot_flow, output_dir=output_dir)
            )
        except Exception as e:
            session.status = "error"
            session.error = str(e)
            yield _sse("error", {"message": str(e)})
            return

        session.status = "done"
        session.output_folder = str(out_path)

        yield _sse("complete", {
            "output_folder": str(out_path),
            "folder_name": out_path.name,
            "bot_name": bot_flow.name,
            "intent_count": len(bot_flow.intents),
            "language": bot_flow.language,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# File downloads
# ---------------------------------------------------------------------------

@app.get("/output/{folder_name}/bot_flow.json")
async def download_bot(folder_name: str):
    config = _load_config()
    output_dir = Path(config.get("output_dir", "./output"))
    bot_file = output_dir / folder_name / "bot_flow.json"
    if not bot_file.exists():
        raise HTTPException(status_code=404, detail="Bot file not found")
    return FileResponse(bot_file, media_type="application/json", filename="bot_flow.json")


@app.get("/output/{folder_name}/requirements.json")
async def download_requirements(folder_name: str):
    config = _load_config()
    output_dir = Path(config.get("output_dir", "./output"))
    req_file = output_dir / folder_name / "requirements.json"
    if not req_file.exists():
        raise HTTPException(status_code=404, detail="Requirements file not found")
    return FileResponse(req_file, media_type="application/json", filename="requirements.json")


@app.get("/output")
async def list_outputs():
    config = _load_config()
    output_dir = Path(config.get("output_dir", "./output"))
    if not output_dir.exists():
        return {"outputs": []}

    outputs = []
    for d in sorted(output_dir.iterdir()):
        if not d.is_dir():
            continue
        entry = {
            "folder": d.name,
            "has_requirements": (d / "requirements.json").exists(),
            "has_bot_flow": (d / "bot_flow.json").exists(),
        }
        req_file = d / "requirements.json"
        if req_file.exists():
            try:
                data = json.loads(req_file.read_text(encoding="utf-8"))
                entry["business_name"] = data.get("business_name", "")
            except Exception:
                pass
        outputs.append(entry)

    return {"outputs": outputs}


# ---------------------------------------------------------------------------
# Static file serving — MUST come after all API routes
# ---------------------------------------------------------------------------

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_spa():
    index = static_dir / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>UI not found</h1><p>static/index.html is missing.</p>", status_code=404)
    return HTMLResponse(index.read_text(encoding="utf-8"))


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    index = static_dir / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
