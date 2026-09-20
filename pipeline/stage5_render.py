"""Stage 5: render the long video and Shorts.

Remotion's bundled ffmpeg/ffprobe binaries were found to be blocked by
Windows Smart App Control on this machine (crashes on every invocation, not
just this project's). To work around that without touching that OS policy,
Remotion is only used to render a PNG frame sequence (the Rust compositor,
not the bundled ffmpeg, does that); the system ffmpeg then encodes the
sequence to video AND muxes on voice, ducked background music, and
chapter-change SFX. If ElevenLabs voice (stage 4) isn't available yet,
placeholder word timestamps and placeholder audio tones are synthesized so
the render can still be exercised end-to-end.
"""

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

from .clients.ffmpeg_utils import synth_tone
from .utils.cache import load_stage, output_dir_for, save_stage
from .utils.config import ROOT, load_config
from .utils.logging import get_logger

STAGE_NAME = "stage5_render"
REMOTION_DIR = ROOT / "remotion"
WORDS_PER_SECOND = 2.5


def _synthetic_word_timestamps(script: str) -> list:
    words = script.split()
    out = []
    t = 0.0
    for w in words:
        dur = max(0.12, len(w) / 9) / WORDS_PER_SECOND * 2.5
        out.append({"word": w, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur
    return out


def _copy_asset(src: Path, public_dir: Path, name: str) -> str:
    dest = public_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return name.replace("\\", "/")


def _resolve_shot_image(
    shot: dict,
    stage3: dict,
    out_dir: Path,
    public_dir: Path,
    pools: dict,
    counters: dict,
) -> dict:
    resolved = dict(shot)
    motion = shot["motion"]
    asset_type = shot["asset_type"]
    ref = shot.get("asset_ref", "") or ""

    if motion == "data_animation":
        resolved["counterLabel"] = shot.get("notes") or None
        return resolved

    if motion == "parallax" and stage3.get("parallax"):
        resolved["image"] = _copy_asset(
            out_dir / stage3["parallax"]["foreground"], public_dir, "parallax_fg.png"
        )
        resolved["backgroundImage"] = _copy_asset(
            out_dir / stage3["parallax"]["background"], public_dir, "parallax_bg.jpg"
        )
        return resolved

    if motion == "reveal":
        resolved["image"] = _copy_asset(out_dir / stage3["main_image"], public_dir, "reveal_main.jpg")
        return resolved

    illustration_by_id = {i["id"]: i["path"] for i in stage3.get("illustrations", [])}
    if asset_type == "illustration" and ref in illustration_by_id:
        src_rel = illustration_by_id[ref]
    else:
        pool = pools.get(asset_type) or pools.get("museum_image_crop") or [stage3["main_image"]]
        i = counters.get(asset_type, 0) % len(pool)
        counters[asset_type] = i + 1
        src_rel = pool[i]

    src = out_dir / src_rel
    dest_name = f"shot_{asset_type}_{abs(hash(src_rel)) % 100000}{Path(src_rel).suffix}"
    resolved["image"] = _copy_asset(src, public_dir, dest_name)
    return resolved


def _build_pools(stage3: dict) -> dict:
    return {
        "museum_image_crop": stage3.get("detail_crops") or [stage3["main_image"]],
        "comparison_object": [c["path"] for c in stage3.get("comparison_objects", [])] or [stage3["main_image"]],
        "illustration": [i["path"] for i in stage3.get("illustrations", [])] or [stage3["main_image"]],
    }


def _derive_shorts_shot_list(long_shots: list, target_total: float = 35.0, max_shots: int = 10) -> list:
    if not long_shots:
        return []
    step = max(1, len(long_shots) // max_shots)
    picked = long_shots[::step][:max_shots]
    per_shot = target_total / len(picked)
    return [{**s, "duration_sec": round(per_shot, 2)} for s in picked]


def _chapter_cue_seconds(shots: list) -> list:
    cues = []
    t = 0.0
    last_chapter = None
    for s in shots:
        if s["chapter"] != last_chapter:
            cues.append(round(t, 3))
            last_chapter = s["chapter"]
        t += s["duration_sec"]
    return cues


def _prepare_audio_files(
    stage4: Optional[dict],
    audio_key: str,
    audio_dir: Path,
    cfg: dict,
    total_duration: float,
    prefix: str,
    out_dir: Path,
) -> dict:
    music_dir = ROOT / cfg["audio"]["background_music_dir"]
    sfx_path = ROOT / cfg["audio"]["chapter_change_sfx"]
    audio_dir.mkdir(parents=True, exist_ok=True)

    if stage4 and stage4.get(audio_key):
        voice_path = out_dir / stage4[audio_key]
    else:
        voice_path = audio_dir / f"{prefix}_voice_placeholder.mp3"
        synth_tone(voice_path, freq=220, duration=total_duration, volume=0.04)

    if music_dir.exists() and any(music_dir.glob("*.mp3")):
        music_path = next(music_dir.glob("*.mp3"))
    else:
        music_path = audio_dir / f"{prefix}_music_placeholder.mp3"
        synth_tone(music_path, freq=110, duration=max(total_duration, 5), volume=0.03)

    if sfx_path.exists():
        sfx_path_resolved = sfx_path
    else:
        sfx_path_resolved = audio_dir / f"{prefix}_sfx_placeholder.mp3"
        synth_tone(sfx_path_resolved, freq=880, duration=0.2, volume=0.15)

    return {
        "voice_path": voice_path,
        "music_path": music_path,
        "sfx_path": sfx_path_resolved,
        "duck_gain": 10 ** (-((cfg["audio"]["music_duck_db_min"] + cfg["audio"]["music_duck_db_max"]) / 2) / 20),
    }


def _prepare_props(
    stage2: dict,
    stage3: dict,
    stage4: Optional[dict],
    out_dir: Path,
    public_dir: Path,
    cfg: dict,
) -> tuple:
    pools = _build_pools(stage3)

    long_counters: dict = {}
    long_shots = [
        _resolve_shot_image(s, stage3, out_dir, public_dir, pools, long_counters)
        for s in stage2["shot_list"]
    ]

    shorts_counters: dict = {}
    shorts_raw = _derive_shorts_shot_list(stage2["shot_list"])
    shorts_shots = [
        _resolve_shot_image(s, stage3, out_dir, public_dir, pools, shorts_counters)
        for s in shorts_raw
    ]

    if stage4 and stage4.get("long_word_timestamps"):
        long_words = stage4["long_word_timestamps"]
    else:
        long_words = _synthetic_word_timestamps(stage2["long_script"])

    if stage4 and stage4.get("shorts_word_timestamps"):
        shorts_words = stage4["shorts_word_timestamps"]
    else:
        shorts_words = _synthetic_word_timestamps(stage2["shorts_script"])

    brand = {
        "accent": cfg["brand"]["colors"]["accent"],
        "background": cfg["brand"]["colors"]["background"],
        "text": cfg["brand"]["colors"]["text"],
        "keywordAccent": cfg["brand"]["colors"]["subtitle_keyword_accent"],
    }

    long_props = {"shotList": long_shots, "wordTimestamps": long_words, "brand": brand}
    shorts_props = {"shotList": shorts_shots, "wordTimestamps": shorts_words, "brand": brand}
    return long_props, shorts_props


def _render_sequence(composition_id: str, props_path: Path, seq_dir: Path) -> None:
    """Render a PNG sequence instead of a video. Remotion's own video encoding
    step also shells out to its bundled ffmpeg, which is unreliable here (see
    module docstring) -- rendering stills only uses the Rust compositor, which
    works fine, and we encode the sequence ourselves with the system ffmpeg.
    """
    seq_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "npx", "remotion", "render", "src/index.ts", composition_id, str(seq_dir),
            f"--props={props_path}", "--port=3217", "--sequence", "--image-format=png",
        ],
        cwd=str(REMOTION_DIR),
        check=True,
        shell=True,
    )


def _normalize_sequence(seq_dir: Path) -> str:
    """Rename Remotion's output frames (whose zero-padding width varies with
    frame count) to a fixed-width sequence ffmpeg can consume reliably."""
    files = sorted(seq_dir.glob("*.png"))
    if not files:
        raise RuntimeError(f"no rendered frames found in {seq_dir}")
    for i, f in enumerate(files):
        target = seq_dir / f"frame_{i:05d}.png"
        if f != target:
            f.rename(target)
    return "frame_%05d.png"


def _encode_sequence(seq_dir: Path, fps: int, out_path: Path) -> None:
    pattern = _normalize_sequence(seq_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", str(fps), "-i", str(seq_dir / pattern),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg sequence encode failed for {out_path}:\n{result.stderr[-3000:]}")


def _mux_audio(
    silent_video: Path,
    voice_path: Path,
    music_path: Path,
    sfx_path: Path,
    cue_seconds: list,
    duck_gain: float,
    duration: float,
    out_path: Path,
) -> None:
    inputs = ["-i", str(silent_video), "-i", str(voice_path), "-stream_loop", "-1", "-i", str(music_path)]
    sfx_start_index = 3
    for _ in cue_seconds:
        inputs += ["-i", str(sfx_path)]

    filters = [f"[2:a]atrim=0:{duration},volume={duck_gain:.4f}[music]"]
    mix_labels = ["1:a", "music"]
    for i, t in enumerate(cue_seconds):
        ms = max(0, int(t * 1000))
        label = f"sfx{i}"
        filters.append(f"[{sfx_start_index + i}:a]adelay={ms}|{ms}[{label}]")
        mix_labels.append(label)
    mix_inputs = "".join(f"[{l}]" for l in mix_labels)
    filters.append(f"{mix_inputs}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0[aout]")

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio mux failed for {out_path}:\n{result.stderr[-3000:]}")


def run(
    stage1_result: dict,
    stage2_result: dict,
    stage3_result: dict,
    stage4_result: Optional[dict],
    run_date: Optional[date] = None,
    force: bool = False,
) -> dict:
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(STAGE_NAME, run_date)
        if cached is not None:
            logger.info("stage5: using cached render")
            return cached

    cfg = load_config()
    out_dir = output_dir_for(run_date)
    date_str = (run_date or date.today()).isoformat()
    public_dir = REMOTION_DIR / "public" / "render" / date_str
    if public_dir.exists():
        shutil.rmtree(public_dir)
    public_dir.mkdir(parents=True, exist_ok=True)

    logger.info("stage5: preparing props and copying image assets into remotion/public")
    long_props, shorts_props = _prepare_props(
        stage2_result, stage3_result, stage4_result, out_dir, public_dir, cfg
    )

    for shot in long_props["shotList"] + shorts_props["shotList"]:
        if shot.get("image"):
            shot["image"] = f"render/{date_str}/{shot['image']}"
        if shot.get("backgroundImage"):
            shot["backgroundImage"] = f"render/{date_str}/{shot['backgroundImage']}"

    long_props_path = REMOTION_DIR / "sample-props" / "long.json"
    shorts_props_path = REMOTION_DIR / "sample-props" / "shorts.json"
    long_props_path.write_text(json.dumps(long_props, ensure_ascii=False), encoding="utf-8")
    shorts_props_path.write_text(json.dumps(shorts_props, ensure_ascii=False), encoding="utf-8")

    audio_dir = out_dir / "audio_render"
    long_total = sum(s["duration_sec"] for s in long_props["shotList"]) or 1.0
    shorts_total = sum(s["duration_sec"] for s in shorts_props["shotList"]) or 1.0
    long_audio = _prepare_audio_files(stage4_result, "long_audio", audio_dir, cfg, long_total, "long", out_dir)
    shorts_audio = _prepare_audio_files(
        stage4_result, "shorts_audio", audio_dir, cfg, shorts_total, "shorts", out_dir
    )

    long_seq_dir = out_dir / "long_frames"
    shorts_seq_dir = out_dir / "shorts_frames"
    long_silent = out_dir / "long_silent.mp4"
    shorts_silent = out_dir / "shorts_silent.mp4"
    long_out = out_dir / "long.mp4"
    shorts_out = out_dir / "shorts.mp4"

    logger.info(
        "stage5: rendering long video picture (%d shots, %.1fs)",
        len(long_props["shotList"]), long_total,
    )
    _render_sequence("LongVideo", long_props_path, long_seq_dir)
    _encode_sequence(long_seq_dir, cfg["video"]["long"]["fps"], long_silent)
    shutil.rmtree(long_seq_dir)

    logger.info(
        "stage5: rendering Shorts picture (%d shots, %.1fs)",
        len(shorts_props["shotList"]), shorts_total,
    )
    _render_sequence("Shorts", shorts_props_path, shorts_seq_dir)
    _encode_sequence(shorts_seq_dir, cfg["video"]["shorts"]["fps"], shorts_silent)
    shutil.rmtree(shorts_seq_dir)

    logger.info("stage5: muxing audio onto long video with ffmpeg")
    long_cues = _chapter_cue_seconds(long_props["shotList"])
    _mux_audio(
        long_silent, long_audio["voice_path"], long_audio["music_path"], long_audio["sfx_path"],
        long_cues, long_audio["duck_gain"], long_total, long_out,
    )

    logger.info("stage5: muxing audio onto Shorts with ffmpeg")
    shorts_cues = _chapter_cue_seconds(shorts_props["shotList"])
    _mux_audio(
        shorts_silent, shorts_audio["voice_path"], shorts_audio["music_path"], shorts_audio["sfx_path"],
        shorts_cues, shorts_audio["duck_gain"], shorts_total, shorts_out,
    )

    long_silent.unlink(missing_ok=True)
    shorts_silent.unlink(missing_ok=True)

    result = {
        "long_video": str(long_out.relative_to(out_dir)),
        "shorts_video": str(shorts_out.relative_to(out_dir)),
    }
    save_stage(STAGE_NAME, result, run_date)
    logger.info("stage5: done")
    return result


if __name__ == "__main__":
    from .stage1_pick_object import run as run_stage1
    from .stage2_generate_script import run as run_stage2
    from .stage3_assets import run as run_stage3
    from .stage4_voice import run as run_stage4

    s1 = run_stage1()
    s2 = run_stage2(s1)
    s3 = run_stage3(s1, s2)
    try:
        s4 = run_stage4(s2)
    except Exception:
        s4 = None
    result = run(s1, s2, s3, s4, force=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
