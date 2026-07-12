import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import configure_logging
from app.db.database import init_db
from app.routers import chat, assess

configure_logging()
logger = logging.getLogger("luniq")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY is not set - /chat and AI-assisted /assess narrative will fail.")
    if not settings.API_KEY:
        logger.warning("API_KEY is not set - endpoints are UNAUTHENTICATED. Set API_KEY before going to production.")
    yield


app = FastAPI(
    title="LUNIQ Health API",
    description=(
        "Production-oriented API for screening user vitals, providing rule-based + AI-assisted health "
        "assessments, and an agentic OTC health-info chatbot with tool use and persistent memory."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    adapter = logging.LoggerAdapter(logger, {"request_id": request_id})

    adapter.info(f"--> {request.method} {request.url.path}")
    try:
        response = await call_next(request)
    except Exception:
        adapter.exception("Unhandled exception while processing request")
        raise
    duration_ms = (time.time() - start) * 1000
    adapter.info(f"<-- {request.method} {request.url.path} {response.status_code} ({duration_ms:.1f}ms)")
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/", tags=["General"])
def read_root():
    return {
        "message": "Welcome to the LUNIQ Health API",
        "docs_url": "/docs",
        "status": "Running",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health", tags=["General"])
def health_check():
    """Lightweight liveness/readiness endpoint for load balancers / uptime monitors."""
    return {"status": "ok"}


app.include_router(assess.router)
app.include_router(chat.router)
