"""Free, no-key voice synthesis via Microsoft Edge's TTS service (edge-tts).

Used as the default voice provider so the pipeline can run with zero paid
services. edge-tts's WordBoundary events give per-word offsets/durations
(100-nanosecond units) directly -- no separate alignment step needed, unlike
ElevenLabs where word timing has to be collapsed from character timestamps.
"""

import asyncio
from typing import Any, Dict, List

import edge_tts

HUNDRED_NS_PER_SECOND = 10_000_000


async def _synthesize_async(text: str, voice: str, rate: str) -> Dict[str, Any]:
    communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    audio_chunks: List[bytes] = []
    words: List[Dict[str, Any]] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start = chunk["offset"] / HUNDRED_NS_PER_SECOND
            end = (chunk["offset"] + chunk["duration"]) / HUNDRED_NS_PER_SECOND
            words.append({"word": chunk["text"], "start": start, "end": end})
    return {"audio_bytes": b"".join(audio_chunks), "words": words}


def synthesize_with_word_timestamps(text: str, voice: str, rate: str = "+0%") -> Dict[str, Any]:
    return asyncio.run(_synthesize_async(text, voice, rate))
