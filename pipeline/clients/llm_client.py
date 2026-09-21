"""LLM structured-output entry point used by every stage: tries Gemini
(gemini_client, which already retries transient 503s on its own) and, only
if that's still unavailable, falls back to Groq -- both free, so a stalled
or overloaded Gemini doesn't block the whole daily run. If no Groq key is
configured, Gemini's own error is raised unchanged.
"""

from typing import List, Optional, Type, TypeVar

from pydantic import BaseModel

from . import gemini_client, groq_client
from ..utils.config import get_env

T = TypeVar("T", bound=BaseModel)


def generate_structured(prompt: str, schema: Type[T], images: Optional[List[tuple]] = None) -> T:
    try:
        return gemini_client.generate_structured(prompt, schema, images=images)
    except Exception:
        if not get_env("GROQ_API_KEY", required=False):
            raise
        # Groq's text-only chat-completions endpoint has no vision input --
        # drop the images rather than fail the whole run over the fallback
        # path not supporting them.
        return groq_client.generate_structured(prompt, schema)
