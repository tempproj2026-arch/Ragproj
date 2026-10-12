import base64
import io
import time
from pathlib import Path
from typing import List, Union, Optional
from PIL import Image
import requests
from .config import settings
from .logging import get_logger

logger = get_logger("ragcore.embeddings")

_text_model = None
_siglip_model = None
_siglip_processor = None

def get_base_url() -> str:
    """Returns normalized base URL for the embedding endpoints."""
    url = settings.lm_studio_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"

def embed_texts(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Computes 1024-dimensional normalized text embeddings using BAAI/bge-m3.
    In dev: calls the Colab endpoint via HTTP POST /v1/embeddings.
    In prod: loads the offline model locally from settings.bge_m3_path.
    """
    if not texts:
        return []

    is_dev = getattr(settings, "environment", "prod").lower() == "dev"

    if is_dev:
        base_url = get_base_url()
        endpoint = f"{base_url}/embeddings"
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            payload = {
                "input": batch,
                "model": "BAAI/bge-m3"
            }
            resp = requests.post(endpoint, json=payload, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            # Sort by index to guarantee correct ordering
            items = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in items])

        return all_embeddings

    # Local production offline execution
    global _text_model
    if _text_model is None:
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading local offline BGE-M3 model from {settings.bge_m3_path}...")
        _text_model = SentenceTransformer(
            str(settings.bge_m3_path),
            device=settings.embedding_device
        )

    embeddings = _text_model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False
    )
    return embeddings.tolist()

def embed_figures(image_paths: List[Union[str, Path]], batch_size: int = 16) -> List[List[float]]:
    """
    Computes 1152-dimensional normalized visual figure embeddings using Google SigLIP.
    In dev: sends base64 images to Colab via POST /v1/figure-embeddings.
    In prod: loads offline SigLIP model locally from settings.siglip_path.
    """
    if not image_paths:
        return []

    is_dev = getattr(settings, "environment", "prod").lower() == "dev"

    if is_dev:
        base_url = get_base_url()
        endpoint = f"{base_url}/figure-embeddings"
        all_embeddings = []

        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]
            b64_list = []
            for p in batch_paths:
                p = Path(p)
                with Image.open(p) as img:
                    img = img.convert("RGB")
                    # Scale down for efficient transfer if large
                    if max(img.size) > 768:
                        img.thumbnail((768, 768), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    b64_list.append(base64.b64encode(buf.getvalue()).decode("utf-8"))

            payload = {"images": b64_list}
            resp = requests.post(endpoint, json=payload, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            items = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in items])

        return all_embeddings

    # Local production offline execution
    global _siglip_model, _siglip_processor
    if _siglip_model is None:
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import torch
        from transformers import AutoProcessor, AutoModel
        logger.info(f"Loading local offline SigLIP model from {settings.siglip_path}...")
        _siglip_processor = AutoProcessor.from_pretrained(str(settings.siglip_path), local_files_only=True)
        _siglip_model = AutoModel.from_pretrained(
            str(settings.siglip_path),
            local_files_only=True
        ).to(settings.embedding_device).eval()

    import torch
    all_embeddings = []
    for i in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[i:i + batch_size]
        pil_images = [Image.open(p).convert("RGB") for p in batch_paths]
        inputs = _siglip_processor(images=pil_images, return_tensors="pt").to(settings.embedding_device)
        with torch.no_grad():
            feats = _siglip_model.get_image_features(**inputs)
            feats = torch.nn.functional.normalize(feats, p=2, dim=1)
        all_embeddings.extend(feats.cpu().float().tolist())

    return all_embeddings
