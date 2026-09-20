"""Stage 4: ElevenLabs voice for the long script and Shorts script, with
word-level timestamps (for per-word animated subtitles) derived from
ElevenLabs' character-level alignment.
"""

from datetime import date
from pathlib import Path
from typing import Optional

from .clients.elevenlabs_client import characters_to_words, synthesize_with_timestamps
from .utils.cache import load_stage, output_dir_for, save_stage
from .utils.config import load_config
from .utils.logging import get_logger

STAGE_NAME = "stage4_voice"


def _synthesize(text: str, voice_id: str, model_id: str, out_path: Path) -> list:
    result = synthesize_with_timestamps(text, voice_id, model_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(result["audio_bytes"])
    return characters_to_words(result["alignment"])


def run(stage2_result: dict, run_date: Optional[date] = None, force: bool = False) -> dict:
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(STAGE_NAME, run_date)
        if cached is not None:
            logger.info("stage4: using cached voice")
            return cached

    cfg = load_config()
    voice_id = cfg["audio"]["elevenlabs_voice_id"]
    model_id = cfg["audio"]["elevenlabs_model_id"]
    out_dir = output_dir_for(run_date)
    audio_dir = out_dir / "audio"

    logger.info("stage4: synthesizing long-video voice")
    long_words = _synthesize(stage2_result["long_script"], voice_id, model_id, audio_dir / "long.mp3")

    logger.info("stage4: synthesizing Shorts voice")
    shorts_words = _synthesize(stage2_result["shorts_script"], voice_id, model_id, audio_dir / "shorts.mp3")

    result = {
        "long_audio": str((audio_dir / "long.mp3").relative_to(out_dir)),
        "long_word_timestamps": long_words,
        "shorts_audio": str((audio_dir / "shorts.mp3").relative_to(out_dir)),
        "shorts_word_timestamps": shorts_words,
    }
    save_stage(STAGE_NAME, result, run_date)
    logger.info("stage4: done")
    return result


if __name__ == "__main__":
    import json

    from .stage1_pick_object import run as run_stage1
    from .stage2_generate_script import run as run_stage2

    s1 = run_stage1()
    s2 = run_stage2(s1)
    result = run(s2, force=True)
    print(
        json.dumps(
            {
                **result,
                "long_word_timestamps": f"{len(result['long_word_timestamps'])} words",
                "shorts_word_timestamps": f"{len(result['shorts_word_timestamps'])} words",
            },
            indent=2,
        )
    )
