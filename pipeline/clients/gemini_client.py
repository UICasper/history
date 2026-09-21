import time
from typing import Type, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from ..utils.config import get_env

T = TypeVar("T", bound=BaseModel)

_client = None

# Gemini's free tier returns transient 503s ("high demand") fairly often;
# a couple of quick retries absorb a short blip. Anything longer than that,
# llm_client.py fails over to Groq instead of sitting here -- no need for a
# long backoff when there's a fast, free fallback one call away.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SEC = [5, 15]


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_env("GEMINI_API_KEY"))
    return _client


def generate_structured(prompt: str, schema: Type[T], model: str = "gemini-3.5-flash") -> T:
    client = _get_client()
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            break
        except errors.ServerError:
            if attempt == _MAX_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_BACKOFF_SEC[attempt])

    parsed = response.parsed
    if parsed is None:
        # SDK couldn't map the JSON onto the schema; fall back to manual validation
        # so the caller sees a clear pydantic error instead of a silent None.
        parsed = schema.model_validate_json(response.text)
    return parsed
