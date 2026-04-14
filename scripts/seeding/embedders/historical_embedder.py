"""HistoricalEmbeddingEngine — real ai_service calls with exponential backoff retry.

Calls http://ai_service:8000/embed in batches (BGE-small-zh 512-dim).
Graceful degradation: if ai_service is unreachable after all retries,
returns empty list so the pipeline continues without blocking.

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Embedding result dataclass ───────────────────────────────────────────────

class EmbeddingResult:
    """
    Result of embedding a batch of texts.

    Attributes:
        texts: The input texts (order preserved).
        vectors: List of embedding vectors (list[float]), same length as texts.
        failed_indices: Indices into texts that failed to embed.
        model: Embedding model identifier used.
    """

    def __init__(
        self,
        texts: list[str],
        vectors: list[list[float]],
        failed_indices: list[int],
        model: str = "bge-small-zh",
    ):
        self.texts = texts
        self.vectors = vectors
        self.failed_indices = failed_indices
        self.model = model

    @property
    def success_count(self) -> int:
        return len(self.vectors)

    def __repr__(self) -> str:
        return f"<EmbeddingResult {self.success_count}/{len(self.texts)} model={self.model}>"


# ─── Core embedder ────────────────────────────────────────────────────────────

class AIServiceHTTPError(Exception):
    """Raised when all retries are exhausted."""
    def __init__(self, last_status: Optional[int], last_body: str):
        self.last_status = last_status
        self.last_body = last_body
        super().__init__(f" AIService HTTP {last_status}: {last_body[:200]}")


class HistoricalEmbeddingEngine:
    """
    Embeds texts via local ai_service BGE-small endpoint.

    Retry strategy:
      - Up to max_retries attempts (default 3)
      - Exponential backoff: 1s, 2s, 4s … (base=1, factor=2)
      - Capped at max_backoff seconds per attempt
      - Network errors (URLError) AND 5xx HTTP errors trigger retry
      - 4xx HTTP errors → NOT retried (client error, will keep failing)

    Graceful degradation:
      - If all retries fail, embed_with_retry returns []
      - embed_batch returns EmbeddingResult with empty vectors for failed items
      - Pipeline logs warning and continues

    Attributes:
        base_url: URL of the embedding service.
        batch_size: Maximum texts per embed request.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts per call.
        max_backoff: Max seconds to wait between retries.
    """

    DIMENSION = 512  # BGE-small-zh output dimension

    def __init__(
        self,
        base_url: str = "http://ai_service:8000/embed",
        batch_size: int = 32,
        timeout: int = 60,
        max_retries: int = 3,
        max_backoff: float = 10.0,
    ):
        self.base_url = base_url
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        self._last_error: Optional[str] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def embed_with_retry(self, text: str, max_retries: int = 3) -> list[float]:
        """
        Embed a single text with exponential backoff retry.

        Args:
            text: Input text string.
            max_retries: Maximum retry attempts.

        Returns:
            Embedding vector as list[float] (512-dim),
            or empty list if all retries fail.
        """
        attempt = 0
        last_status: Optional[int] = None
        last_body = ""

        while attempt <= max_retries:
            try:
                vectors = self._call_api([text])
                self._last_error = None
                return vectors[0]
            except AIServiceHTTPError as exc:
                last_status = exc.last_status
                last_body = exc.last_body
                # Don't retry 4xx errors
                if last_status is not None and 400 <= last_status < 500:
                    logger.warning(
                        "AIService returned client error %d — not retrying: %s",
                        last_status, last_body[:100],
                    )
                    break
                attempt += 1
                if attempt > max_retries:
                    break
                backoff = min(2 ** (attempt - 1), self.max_backoff)
                logger.warning(
                    "Embed attempt %d/%d failed (HTTP %s) — retrying in %.1fs",
                    attempt, max_retries, last_status, backoff,
                )
                time.sleep(backoff)
            except Exception as exc:
                last_body = str(exc)
                attempt += 1
                if attempt > max_retries:
                    break
                backoff = min(2 ** (attempt - 1), self.max_backoff)
                logger.warning(
                    "Embed attempt %d/%d failed (%s) — retrying in %.1fs",
                    attempt, max_retries, exc, backoff,
                )
                time.sleep(backoff)

        self._last_error = f"HTTP {last_status}: {last_body[:200]}" if last_status else last_body[:200]
        logger.error(
            "Embed failed after %d attempts for text(len=%d): %s",
            max_retries + 1, len(text), self._last_error,
        )
        return []

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """
        Embed a batch of texts efficiently.

        Splits into sub-batches of self.batch_size and makes sequential
        HTTP requests, collecting results and tracking failures.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with vectors (order-preserving) and failed indices.
        """
        if not texts:
            return EmbeddingResult(texts=[], vectors=[], failed_indices=[])

        all_vectors: list[list[float]] = []
        failed_indices: list[int] = []

        for batch_start in range(0, len(texts), self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            try:
                vectors = self._call_api_with_retry(batch)
                if len(vectors) < len(batch):
                    # Partial failure — pad with empty vectors
                    logger.warning(
                        "Partial embed failure: requested %d, got %d — padding with []",
                        len(batch), len(vectors),
                    )
                    batch_failed_start = len(all_vectors)
                    all_vectors.extend(vectors)
                    all_vectors.extend([] for _ in range(len(batch) - len(vectors)))
                    failed_indices.extend(range(batch_failed_start, batch_failed_start + len(batch) - len(vectors)))
                else:
                    all_vectors.extend(vectors)
            except Exception as exc:
                logger.warning(
                    "Batch embed failed for indices %d-%d: %s — marking as failed",
                    batch_start, batch_start + len(batch) - 1, exc,
                )
                batch_start_idx = len(all_vectors)
                all_vectors.extend([] for _ in batch)
                failed_indices.extend(range(batch_start_idx, batch_start_idx + len(batch)))

        return EmbeddingResult(
            texts=texts,
            vectors=all_vectors,
            failed_indices=failed_indices,
        )

    def get_last_error(self) -> Optional[str]:
        """Return the error message from the last failed request, or None."""
        return self._last_error

    # ── Internal HTTP ──────────────────────────────────────────────────────────

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Make a single HTTP call to the embed endpoint (no retry)."""
        payload = {"texts": texts}
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8") if exc.fp else ""
            raise AIServiceHTTPError(exc.code, body) from exc
        except urllib.error.URLError as exc:
            raise AIServiceHTTPError(None, str(exc.reason)) from exc

        embeddings = result.get("embeddings", [])
        if not embeddings and texts:
            raise AIServiceHTTPError(None, f"empty embeddings for {len(texts)} texts")
        return embeddings

    def _call_api_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Call _call_api with exponential backoff retry."""
        attempt = 0
        last_status: Optional[int] = None
        last_body = ""

        while attempt <= self.max_retries:
            try:
                return self._call_api(texts)
            except AIServiceHTTPError as exc:
                last_status = exc.last_status
                last_body = exc.last_body
                if last_status is not None and 400 <= last_status < 500:
                    raise
                attempt += 1
                if attempt > self.max_retries:
                    raise AIServiceHTTPError(last_status, last_body)
                backoff = min(2 ** (attempt - 1), self.max_backoff)
                logger.warning(
                    "Batch embed HTTP %s — retry %d/%d in %.1fs",
                    last_status, attempt, self.max_retries, backoff,
                )
                time.sleep(backoff)
            except Exception as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                backoff = min(2 ** (attempt - 1), self.max_backoff)
                logger.warning(
                    "Batch embed error %s — retry %d/%d in %.1fs",
                    exc, attempt, self.max_retries, backoff,
                )
                time.sleep(backoff)

        return []
