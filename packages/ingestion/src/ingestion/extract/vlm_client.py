import base64
import io
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image
from openai import OpenAI

from ragcore.config import settings
from ragcore.paths import get_data_root, get_book_dir, get_page_dir, resolve_path
from ragcore.logging import get_logger

logger = get_logger("ingestion.extract.vlm_client")

_client: Optional[OpenAI] = None

def get_vlm_client() -> OpenAI:
    """Returns singleton OpenAI-compatible client pointing to settings.lm_studio_url."""
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=settings.lm_studio_url,
            api_key="none",
            timeout=180.0
        )
    return _client

def encode_image_base64(image_path: Path, max_dim: int = 1280) -> str:
    """
    Reads an image, downscales it so the longest edge is at most max_dim
    (preventing GPU OOM on large scanned full pages while preserving fine text),
    and returns a base64 encoded JPEG string.
    """
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            new_w = int(round(w * scale))
            new_h = int(round(h * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

PROMPTS = {
    "table": (
        "You are an expert document digitization assistant. Read this scanned table image with absolute precision. "
        "Transcribe the table into clean GitHub Flavored Markdown format. "
        "Every single number, decimal point, unit, column header, and row label MUST be transcribed exactly as printed. "
        "Do not invent or omit any rows or numbers. Output only the markdown table and caption if present."
    ),
    "formula": (
        "You are an expert mathematical document digitizer. Transcribe the formula or equation from this scanned image "
        "into LaTeX format (e.g. $$ ... $$). Include any surrounding explanations of what the variables represent. "
        "Preserve every exponent, subscript, fraction, constant, and variable name accurately."
    ),
    "figure": (
        "You are an expert technical illustrator and document analyzer. Describe this technical diagram, chart, or figure in detail. "
        "Identify the title or figure number (e.g. 'Figure 3'), all labeled components, arrows, inputs, outputs, and the technical purpose. "
        "Quote any text or labels printed inside the image verbatim so this figure can be accurately searched."
    ),
    "text": (
        "You are an expert OCR transcription assistant. Transcribe the text from this scanned book page region verbatim. "
        "Preserve paragraph structure, section headers, numbers, formulas, and exact wording without summarization."
    )
}

def call_vlm_for_image(
    image_path: Path,
    kind: str = "text",
    max_retries: int = 3
) -> str:
    """
    Sends a cropped region image to the vision-language model via the OpenAI-compatible API.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    is_dev = getattr(settings, "environment", "prod").lower() == "dev"
    max_dim = 768 if is_dev else 1280
    max_tokens = 512 if is_dev else 2048

    b64_img = encode_image_base64(image_path, max_dim=max_dim)
    prompt = PROMPTS.get(kind, PROMPTS["text"])
    client = get_vlm_client()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_img}"
                    }
                }
            ]
        }
    ]

    last_err = None
    for attempt in range(max_retries):
        try:
            t0 = time.time()
            response = client.chat.completions.create(
                model=settings.vision_model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=max_tokens
            )
            duration = time.time() - t0
            content = response.choices[0].message.content.strip()
            logger.info(f"VLM call ({kind}, {image_path.name}) completed in {duration:.2f}s ({len(content)} chars)")
            return content
        except Exception as e:
            last_err = e
            logger.warning(f"VLM call attempt {attempt + 1} failed: {e}. Retrying in 3s...")
            time.sleep(3)

    raise RuntimeError(f"Failed VLM call for {image_path} after {max_retries} attempts: {last_err}")

def extract_page_regions_vlm(
    book_slug: str,
    page_number: int,
    force: bool = False
) -> Dict[str, Any]:
    """
    Iterates through all cropped regions on a page, calls the VLM to transcribe them,
    assembles `page.md` in reading order, and updates `page.json`.
    """
    page_dir = get_page_dir(book_slug, page_number)
    page_json_path = page_dir / "page.json"
    page_md_path = page_dir / "page.md"

    if not page_json_path.exists():
        raise FileNotFoundError(f"page.json not found for {book_slug} p{page_number:04d}")

    with open(page_json_path, "r", encoding="utf-8") as f:
        page_meta = json.load(f)

    regions = page_meta.get("regions", [])
    if not regions:
        return {"status": "skipped", "reason": "no regions"}

    extracted_contents = []
    updated_regions = []

    for reg in regions:
        rel_img_path = reg.get("image_path")
        kind = reg.get("kind", "text")
        needs_vlm = reg.get("needs_vlm", False)

        if needs_vlm and rel_img_path:
            abs_img_path = resolve_path(rel_img_path)
            # Skip if already extracted unless force=True
            if not force and reg.get("extracted_text"):
                extracted_text = reg["extracted_text"]
            else:
                extracted_text = call_vlm_for_image(abs_img_path, kind=kind)
                reg["extracted_text"] = extracted_text
                reg["vlm_model"] = settings.vision_model_name
        else:
            # Text was already extracted by Docling OCR
            extracted_text = reg.get("extracted_text", "")

        updated_regions.append(reg)
        extracted_contents.append(f"<!-- region:{reg.get('id')} kind:{kind} -->\n{extracted_text}\n")

    # Assemble page.md
    page_md_content = f"# Book: {book_slug} - Page {page_number}\n\n" + "\n".join(extracted_contents)
    with open(page_md_path, "w", encoding="utf-8") as f:
        f.write(page_md_content)

    page_meta["regions"] = updated_regions
    page_meta["status"] = "vlm_extracted"
    page_meta["vlm_model"] = settings.vision_model_name

    with open(page_json_path, "w", encoding="utf-8") as f:
        json.dump(page_meta, f, indent=2)

    return {
        "book_slug": book_slug,
        "page_number": page_number,
        "regions_extracted": len(updated_regions),
        "page_md_path": str(page_md_path)
    }

if __name__ == "__main__":
    res = extract_page_regions_vlm("chapter_1_2_3_scanned", 1, force=True)
    print(res)
