import subprocess
from pathlib import Path


def synth_tone(out_path: Path, freq: int, duration: float, volume: float = 0.08) -> None:
    """Synthesize a placeholder audio tone (silence-ish sine wave) with ffmpeg.

    Used only as a stand-in for real ElevenLabs voice / CC0 music/SFX so the
    render pipeline can be exercised end-to-end before those assets exist.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.05, duration)
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
            "-af", f"volume={volume},afade=t=in:d=0.02,afade=t=out:st={max(0, duration - 0.05)}:d=0.05",
            "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-ac", "1",
            str(out_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed synthesizing {out_path}:\n{result.stderr[-2000:]}")
