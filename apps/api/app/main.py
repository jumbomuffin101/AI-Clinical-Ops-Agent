import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import get_settings
from app.db.session import Base, engine
from app.logging_utils import log_event
from app.models import db as _db_models
from app.routes import debug, evaluation, health, notes

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importing model definitions registers tables on SQLAlchemy metadata for local create_all.
_ = _db_models
if settings.auto_create_tables and settings.environment.lower() in {"local", "test"}:
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event(
        logger,
        logging.INFO,
        "llm.startup.config",
        selected_provider=settings.llm_provider.strip().lower() or "mock",
        groq_key_loaded=bool(settings.groq_api_key),
        groq_model=settings.groq_model,
        openrouter_key_loaded=bool(settings.openrouter_api_key),
        openrouter_model=settings.openrouter_model,
    )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_bytes:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request_too_large",
                    "message": f"Request body must be {settings.max_request_bytes} bytes or smaller.",
                }
            },
        )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": exc.detail}},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_server_error", "message": "Unexpected API error."}},
    )


app.include_router(health.router)
app.include_router(notes.router)
app.include_router(evaluation.router)
app.include_router(debug.router)
