import base64
from typing import Any, Dict, List

import requests

from ..utils.config import get_env

BASE = "https://api.elevenlabs.io/v1"


def synthesize_with_timestamps(text: str, voice_id: str, model_id: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{BASE}/text-to-speech/{voice_id}/with-timestamps",
        headers={
            "xi-api-key": get_env("ELEVENLABS_API_KEY"),
            "Content-Type": "application/json",
        },
        json={"text": text, "model_id": model_id},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "audio_bytes": base64.b64decode(data["audio_base64"]),
        "alignment": data["alignment"],
    }


def characters_to_words(alignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collapse ElevenLabs' character-level alignment into per-word start/end times."""
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]

    words = []
    current = ""
    word_start = None
    word_end = None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if current:
                words.append({"word": current, "start": word_start, "end": word_end})
                current = ""
                word_start = None
        else:
            if word_start is None:
                word_start = s
            current += ch
            word_end = e
    if current:
        words.append({"word": current, "start": word_start, "end": word_end})
    return words
