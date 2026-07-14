"""Vision provider abstraction for amigurumi image analysis.

Set VISION_PROVIDER in .env to switch providers:
  VISION_PROVIDER=gemini   (default) — requires GOOGLE_API_KEY
  VISION_PROVIDER=claude             — requires ANTHROPIC_API_KEY
  VISION_PROVIDER=ollama             — requires a running Ollama server with a vision model
  VISION_PROVIDER=agnes              — requires AGNES_API_KEY (OpenAI-compatible API)
"""

import base64
import json
import logging
import os

logger = logging.getLogger(__name__)

# Shared JSON schema used by Claude (tool input_schema) and Ollama (format param).
# Gemini uses its own TypedDict-based schema enforced natively.
_PARTS_SCHEMA = {
    "type": "object",
    "properties": {
        "parts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "sphere", "cylinder", "cone", "frustum",
                            "capsule", "teardrop", "flat_disc", "torus",
                        ],
                    },
                    "scale": {"type": "number"},
                    # Optional normalized 2D bounding box in image coords
                    # [x_min, y_min, x_max, y_max], all in [0, 1], image-y points down.
                    # Downstream mesh measurement uses these to slice the .glb per part.
                    # Providers that can't comply may omit it; consumers must treat it as optional.
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                },
                "required": ["name", "type", "scale"],
            },
        }
    },
    "required": ["parts"],
}


def analyze_image(img_bytes: bytes, prompt: str) -> dict:
    """Analyze a JPEG image and return {"parts": [{"name", "type", "scale"}, ...]}."""
    provider = os.environ.get("VISION_PROVIDER", "gemini").lower()
    if provider == "gemini":
        return _analyze_gemini(img_bytes, prompt)
    if provider == "claude":
        return _analyze_claude(img_bytes, prompt)
    if provider == "ollama":
        return _analyze_ollama(img_bytes, prompt)
    if provider == "agnes":
        return _analyze_agnes(img_bytes, prompt)
    raise ValueError(f"Unknown VISION_PROVIDER '{provider}'. Valid: gemini, claude, ollama, agnes")


def _analyze_gemini(img_bytes: bytes, prompt: str) -> dict:
    from google import genai
    from google.genai import types
    import typing_extensions as te
    from typing import List

    class PartNode(te.TypedDict):
        name: str
        type: te.Literal[
            "sphere", "cylinder", "cone", "frustum",
            "capsule", "teardrop", "flat_disc", "torus",
        ]
        scale: float
        bbox: te.NotRequired[List[float]]

    class DependencyGraph(te.TypedDict):
        parts: List[PartNode]

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[prompt, types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DependencyGraph,
        ),
    )
    return json.loads(response.text)


def _analyze_claude(img_bytes: bytes, prompt: str) -> dict:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed — run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
    img_b64 = base64.standard_b64encode(img_bytes).decode()

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[{
            "name": "analyze_amigurumi",
            "description": "Return the geometric decomposition of the doll in the image.",
            "input_schema": _PARTS_SCHEMA,
        }],
        tool_choice={"type": "tool", "name": "analyze_amigurumi"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Claude response contained no tool_use block")


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences if the model wraps its JSON output."""
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def _analyze_agnes(img_bytes: bytes, prompt: str) -> dict:
    """OpenAI-compatible chat-completions provider (Agnes AI)."""
    import requests

    base_url = os.environ.get("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1").rstrip("/")
    api_key = os.environ.get("AGNES_API_KEY")
    if not api_key:
        raise RuntimeError("AGNES_API_KEY is not set")
    model = os.environ.get("AGNES_MODEL", "agnes-2.0-flash")
    img_b64 = base64.standard_b64encode(img_bytes).decode()

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": (
                        prompt
                        + "\n\nRespond with ONLY a valid JSON object matching this schema"
                        " (no markdown, no explanation):\n"
                        + json.dumps(_PARTS_SCHEMA)
                    )},
                ],
            }],
            "response_format": {"type": "json_object"},
            "max_tokens": 2048,
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    return json.loads(_strip_code_fences(text))


def _analyze_ollama(img_bytes: bytes, prompt: str) -> dict:
    import requests

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llava")
    img_b64 = base64.standard_b64encode(img_bytes).decode()

    resp = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt + "\n\nRespond with ONLY a valid JSON object. No markdown, no explanation.",
            "images": [img_b64],
            "format": _PARTS_SCHEMA,  # Ollama 0.5+ structured output
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json().get("response", "").strip()
    return json.loads(_strip_code_fences(text))


# ─── Silent-retry wrapper for under-segmenting providers ──────────────────────

_MIN_PARTS = 4
_RETRY_SUFFIX = (
    "\n\nIMPORTANT: include ALL visible body parts — head, body, BOTH arms, "
    "BOTH legs, ears, tail, etc. Do not omit symmetric parts."
)


def _passes_threshold(response: dict) -> bool:
    parts = response.get("parts") or []
    if len(parts) < _MIN_PARTS:
        return False
    names = [str(p.get("name", "")).lower() for p in parts]
    has_head = any("head" in n for n in names)
    has_body = any("body" in n or "torso" in n for n in names)
    return has_head and has_body


def analyze_with_retry(img_bytes: bytes, prompt: str, max_retries: int = 2) -> dict:
    """Call analyze_image; if the response misses core parts, retry silently
    with a strengthened prompt. Returns the last response regardless of success."""
    response = analyze_image(img_bytes, prompt)
    if _passes_threshold(response):
        return response
    strengthened = prompt + _RETRY_SUFFIX
    for attempt in range(1, max_retries + 1):
        logger.info("vision retry %d/%d: undersegmented response (%d parts)",
                    attempt, max_retries, len(response.get("parts") or []))
        response = analyze_image(img_bytes, strengthened)
        if _passes_threshold(response):
            return response
    return response
