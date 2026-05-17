# app/main.py
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.logger import get_logger, StructuredLoggingMiddleware

app = FastAPI(title="TIS API", version="1.0.0")

# ── Sentry initialization ────────────────────────────────────────────────────
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    environment=os.environ.get("SENTRY_ENV", "development"),
    integrations=[
        FastApiIntegration(transaction_style="url"),
    ],
    ignore_errors=[HTTPException],
    send_default_pii=False,
    traces_sample_rate=0.1,
)

# CORS middleware - allow frontend on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured logging middleware
app.add_middleware(StructuredLoggingMiddleware)

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    log = get_logger("exception")
    log.error("value_error", detail=str(exc))
    return JSONResponse(status_code=400, content={"detail": str(exc)})

from app.api.v1.endpoints import projects, documents, evaluations, rag, pricing, formal_review, review
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(evaluations.router)
app.include_router(rag.router)
app.include_router(pricing.router)
app.include_router(formal_review.router)
app.include_router(review.router)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """Ensure demo user exists on startup (matches frontend authStore hardcoded id=1)."""
    from app.core.logger import get_logger
    from app.db.seed import seed_demo_user

    logger = get_logger("startup")
    try:
        seed_demo_user()
        logger.info("Demo user ensured on startup")
    except Exception as e:
        logger.error(f"Failed to ensure demo user: {e}")
        # Non-blocking: log error only, don't crash startup