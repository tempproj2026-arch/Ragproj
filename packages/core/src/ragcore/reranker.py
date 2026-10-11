import time
from typing import List, Dict, Any, Optional, Tuple
import requests

from .config import settings
from .logging import get_logger

logger = get_logger("ragcore.reranker")

_local_reranker = None

def get_base_url() -> str:
    url = settings.lm_studio_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"

def rerank_documents(
    query: str,
    documents: List[str],
    top_k: Optional[int] = None
) -> List[Tuple[int, float]]:
    """
    Reranks documents against the query using a CrossEncoder (BAAI/bge-reranker-v2-m3).
    Returns list of (original_index, relevance_score) sorted by score descending.

    In dev: attempts to call Colab /v1/rerank. If unavailable, falls back to original order.
    In prod: loads local CrossEncoder model from settings.reranker_path.
    """
    if not documents:
        return []

    top_n = top_k or len(documents)
    is_dev = getattr(settings, "environment", "prod").lower() == "dev"

    if is_dev:
        # Dev mode: Query remote Colab endpoint
        base_url = get_base_url()
        endpoint = f"{base_url}/rerank"
        payload = {
            "query": query,
            "documents": documents,
            "top_n": top_n
        }
        try:
            resp = requests.post(endpoint, json=payload, timeout=15.0)
            if resp.status_code == 200:
                data = resp.json()
                results = [(item["index"], float(item["relevance_score"])) for item in data["results"]]
                return results
            else:
                logger.debug(f"Colab reranker endpoint returned status {resp.status_code}. Using fallback ranking.")
        except Exception as e:
            logger.debug(f"Colab reranker endpoint unreachable ({e}). Using fallback ranking.")

        # Graceful fallback: return original indices with descending dummy rank
        return [(i, 1.0 / (i + 1)) for i in range(min(top_n, len(documents)))]

    # Production offline mode
    global _local_reranker
    if _local_reranker is None:
        from sentence_transformers import CrossEncoder
        logger.info(f"Loading local offline CrossEncoder from {settings.reranker_path}...")
        _local_reranker = CrossEncoder(
            str(settings.reranker_path),
            device=settings.reranker_device
        )

    pairs = [[query, doc] for doc in documents]
    scores = _local_reranker.predict(pairs)

    ranked = sorted(
        [(i, float(score)) for i, score in enumerate(scores)],
        key=lambda x: x[1],
        reverse=True
    )
    return ranked[:top_n]
