import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent.parent / ".env")
from .advice import QUESTIONS, RM_THRESHOLD, recommend
from .chat import handle_chat  # noqa: E402  (after load_dotenv)
from .portfolio import repo, norm_profile  # noqa: E402
from .risk import get_user_risk_profile  # noqa: E402

api = APIRouter(prefix="/api")


class Plan(BaseModel):
    goal: str | None = Field(None, max_length=80)
    horizon: str | None = Field(None, max_length=80)
    amount: str | None = Field(None, max_length=80)
    recommended_id: str | None = Field(None, max_length=10)
    needs_rm: bool = False


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(None, max_length=64)
    selected_portfolio_id: str | None = Field(None, max_length=10)
    profile: str | None = Field(None, max_length=20)
    plan: Plan | None = None


class AdviceRequest(BaseModel):
    profile: str = Field(max_length=20)
    goal: str | None = Field(None, max_length=80)
    horizon: str | None = Field(None, max_length=80)
    amount: str | None = Field(None, max_length=80)


class CompareRequest(BaseModel):
    portfolio_ids: list[str] = Field(min_length=2, max_length=5)


@api.get("/risk-profile")
def risk_profile(profile: str | None = None): return get_user_risk_profile(profile)

@api.get("/portfolios")
def portfolios(): return repo.get_all()

@api.get("/portfolios/profile/{profile}")
def by_profile(profile: str):
    if not norm_profile(profile):
        raise HTTPException(404, "Unknown profile")
    return repo.get_by_profile(profile)

@api.get("/portfolios/{portfolio_id}")
def detail(portfolio_id: str):
    p = repo.get_by_id(portfolio_id)
    if not p:
        raise HTTPException(404, "Portfolio not found")
    return p

@api.post("/portfolios/compare")
def compare(req: CompareRequest):
    try:
        return repo.compare(req.portfolio_ids)
    except ValueError:
        raise HTTPException(400, "Provide at least two valid portfolio ids")

@api.get("/efficient-frontier")
def frontier(): return repo.frontier()

@api.get("/advice/questions")
def advice_questions():
    return {"questions": [{"key": q["key"], "text": q["text"], "options": [o[0] for o in q["options"]]} for q in QUESTIONS],
            "rm": {"threshold": RM_THRESHOLD, "wa_number": os.getenv("RM_WA_NUMBER", "6281200000000")}}

@api.post("/advice/recommend")
def advice(req: AdviceRequest):
    return recommend(req.profile, req.model_dump())

@api.post("/chat")
async def chat(req: ChatRequest):
    return await handle_chat(req.message, req.conversation_id, req.selected_portfolio_id, req.profile,
                             req.plan.model_dump() if req.plan else None)


app = FastAPI(title="Robo Financial Advisor")
app.include_router(api)


@app.exception_handler(HTTPException)
async def http_err(_: Request, e: HTTPException):
    return JSONResponse({"error": True, "message": e.detail}, status_code=e.status_code)

@app.exception_handler(RequestValidationError)
async def val_err(_: Request, e):
    return JSONResponse({"error": True, "message": "Invalid request"}, status_code=422)

@app.exception_handler(Exception)
async def any_err(_: Request, e: Exception):  # never leak stack traces, paths or keys
    return JSONResponse({"error": True, "message": "Unable to process request"}, status_code=500)


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "frontend", html=True), name="frontend")
