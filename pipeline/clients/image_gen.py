"""AI illustration generation: Gemini image gen (primary), Pollinations (free,
no-key fallback) if Gemini is unavailable, over quota, or fails.
"""

import io
import urllib.parse

import requests
from PIL import Image

from ..utils.config import get_env


def _gemini_generate(prompt: str) -> Image.Image:
    from google import genai

    client = genai.Client(api_key=get_env("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=prompt,
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
    raise RuntimeError("Gemini image generation returned no image part")


def _pollinations_generate(prompt: str, width: int, height: int) -> Image.Image:
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}"
    resp = requests.get(
        url, params={"width": width, "height": height, "nologo": "true"}, timeout=90
    )
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def generate_illustration(prompt: str, width: int = 1024, height: int = 1024) -> Image.Image:
    try:
        return _gemini_generate(prompt)
    except Exception:
        return _pollinations_generate(prompt, width, height)
