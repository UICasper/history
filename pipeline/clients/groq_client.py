"""Free, keyed fallback LLM (Groq's OpenAI-compatible REST API) used when
Gemini is unavailable after retries. Plain requests.post, no SDK -- same
style as elevenlabs_client.py, and avoids depending on a package install
succeeding just for the fallback path. No native JSON-schema constraint on
Groq's side -- we ask for JSON mode and validate the result against the
Pydantic schema ourselves, same as gemini_client's own manual-validation
fallback.
"""

import json
from typing import Type, TypeVar

import requests
from pydantic import BaseModel

from ..utils.config import get_env

T = TypeVar("T", bound=BaseModel)

BASE = "https://api.groq.com/openai/v1"


def generate_structured(prompt: str, schema: Type[T], model: str = "openai/gpt-oss-120b") -> T:
    system = (
        "Respond with ONLY a single valid JSON object matching this JSON Schema -- "
        "no markdown code fences, no commentary before or after it:\n"
        + json.dumps(schema.model_json_schema())
    )
    resp = requests.post(
        f"{BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {get_env('GROQ_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.8,
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return schema.model_validate_json(content)
