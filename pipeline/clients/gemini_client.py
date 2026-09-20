from typing import Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from ..utils.config import get_env

T = TypeVar("T", bound=BaseModel)

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_env("GEMINI_API_KEY"))
    return _client


def generate_structured(prompt: str, schema: Type[T], model: str = "gemini-2.5-flash") -> T:
    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    parsed = response.parsed
    if parsed is None:
        # SDK couldn't map the JSON onto the schema; fall back to manual validation
        # so the caller sees a clear pydantic error instead of a silent None.
        parsed = schema.model_validate_json(response.text)
    return parsed
