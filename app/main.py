# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="TIS API", version="1.0.0")

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

from app.api.v1.endpoints import projects, documents, evaluations, rag, pricing, formal_review
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(evaluations.router)
app.include_router(rag.router)
app.include_router(pricing.router)
app.include_router(formal_review.router)

@app.get("/health")
def health():
    return {"status": "ok"}
