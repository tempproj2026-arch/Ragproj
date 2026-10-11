import base64
import os
from pathlib import Path
from typing import Optional

from ragcore.config import settings

def resolve_image_path(rel_or_abs_path: str) -> Path:
    """Resolves a relative or absolute image path to an absolute Path on disk."""
    p = Path(rel_or_abs_path)
    if p.is_absolute():
        return p
    # Resolve relative to data_root
    return Path(settings.data_root) / rel_or_abs_path

def get_image_base64(rel_or_abs_path: str) -> Optional[str]:
    """Reads an image file and returns base64 encoded data URI."""
    full_path = resolve_image_path(rel_or_abs_path)
    if not full_path.exists():
        return None
    
    ext = full_path.suffix.lstrip(".").lower()
    mime = "image/png" if ext == "png" else "image/jpeg"
    with open(full_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"
