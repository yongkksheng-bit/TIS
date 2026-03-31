"""
TIS AI Microservice — BGE-Small + Reranker-Base
RTX 3060 GPU (6GB) | sentence-transformers | FP16
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
import torch
from sentence_transformers import SentenceTransformer, CrossEncoder

# ── Globals ──────────────────────────────────────────────────────────
embedder: SentenceTransformer = None
reranker: CrossEncoder = None

EMBEDDER_MODEL = "BAAI/bge-small-zh-v1.5"  # 512-dim, ~130MB FP16
RERANKER_MODEL = "BAAI/bge-reranker-base"   # Cross-Encoder, ~340MB FP16


# ── Lifespan: Load models on startup ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedder, reranker

    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"

    print(f"🚀 RTX 3060 微服务满血唤醒")
    print(f"   加载 Embedder: {EMBEDDER_MODEL} 到 GPU (FP16) ...")

    embedder = SentenceTransformer(EMBEDDER_MODEL)
    embedder = embedder.to("cuda").half()

    print(f"   加载 Reranker: {RERANKER_MODEL} 到 CPU (FP32) ...")
    reranker = CrossEncoder(RERANKER_MODEL, device="cpu")

    print(f"   ✅ Small + Base Reranker 已极速加载至显存")
    print(f"   ✅ GPU: {gpu_name} | FP16: ON")
    print(f"   ✅ AI 微服务就绪，端口 8000")

    yield

    # shutdown
    del embedder, reranker
    torch.cuda.empty_cache()


# ── FastAPI App ──────────────────────────────────────────────────────
app = FastAPI(title="TIS AI Service", lifespan=lifespan)


# ── Schemas ──────────────────────────────────────────────────────────
class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dimension: int


class RerankRequest(BaseModel):
    query: str
    candidates: list[str]
    top_k: int = 5


class RerankResponse(BaseModel):
    rankings: list[tuple[int, float]]  # (index, score)


# ── Endpoints ─────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "gpu": torch.cuda.is_available()}


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    with torch.no_grad():
        vecs = embedder.encode(
            req.texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    return EmbedResponse(
        embeddings=vecs.tolist(),
        dimension=vecs.shape[1],
    )


@app.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    pairs = [[req.query, c] for c in req.candidates]
    with torch.no_grad():
        scores = reranker.predict(pairs, convert_to_numpy=True)

    ranking = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[: req.top_k]
    return RerankResponse(rankings=ranking)
