"""LLM structured-output entry point used by every stage: tries Gemini
(gemini_client, which already retries transient 503s on its own) and, only
if that's still unavailable, falls back to Groq -- both free, so a stalled
or overloaded Gemini doesn't block the whole daily run. If no Groq key is
configured, Gemini's own error is raised unchanged.
"""

from typing import Type, TypeVar

from pydantic import BaseModel

from . import gemini_client, groq_client
from ..utils.config import get_env

T = TypeVar("T", bound=BaseModel)


def generate_structured(prompt: str, schema: Type[T]) -> T:
    try:
        return gemini_client.generate_structured(prompt, schema)
    except Exception:
        if not get_env("GROQ_API_KEY", required=False):
            raise
        return groq_client.generate_structured(prompt, schema)
