"""Stage 6: render thumbnail variants (1280x720) and the Shorts cover
(1080x1920). Text is rendered in code (Pillow), never by an image model --
only the background object image is AI/museum sourced.
"""

from datetime import date
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .utils.cache import load_stage, output_dir_for, save_stage
from .utils.config import ROOT, load_config
from .utils.logging import get_logger

STAGE_NAME = "stage6_thumbnails"


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    max_width: int,
    max_height: int,
    start_size: int,
    min_size: int = 36,
    line_spacing: float = 1.05,
):
    size = start_size
    while size >= min_size:
        font = ImageFont.truetype(font_path, size)
        words = text.split()
        lines, current = [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        line_height = font.getbbox("Hg")[3] * line_spacing
        total_height = line_height * len(lines)
        widest = max((draw.textlength(l, font=font) for l in lines), default=0)
        if total_height <= max_height and widest <= max_width:
            return font, lines, line_height
        size -= 4
    font = ImageFont.truetype(font_path, min_size)
    return font, [text], font.getbbox("Hg")[3] * line_spacing


def _background_layer(main_img: Image.Image, foreground: Optional[Image.Image], width: int, height: int) -> Image.Image:
    canvas = ImageOps.fit(main_img.convert("RGB"), (width, height), Image.LANCZOS)
    overlay = Image.new("RGB", (width, height), (0, 0, 0))
    canvas = Image.blend(canvas, overlay, 0.4)

    if foreground is not None:
        fg = foreground.convert("RGBA")
        scale = (height * 0.92) / fg.height
        new_size = (max(1, int(fg.width * scale)), max(1, int(fg.height * scale)))
        fg_resized = fg.resize(new_size, Image.LANCZOS)
        x = width - new_size[0] - int(width * 0.03)
        y = height - new_size[1]
        canvas.paste(fg_resized, (x, y), fg_resized)
    return canvas


def _render_thumbnail(
    main_img: Image.Image,
    foreground: Optional[Image.Image],
    text: str,
    cfg: dict,
) -> Image.Image:
    width = cfg["brand"]["thumbnail"]["width"]
    height = cfg["brand"]["thumbnail"]["height"]
    canvas = _background_layer(main_img, foreground, width, height)
    draw = ImageDraw.Draw(canvas)

    font_path = str(ROOT / cfg["brand"]["fonts"]["heading"])
    max_text_width = int(width * 0.56)
    max_text_height = int(height * 0.7)
    font, lines, line_height = _fit_text(
        draw, text.upper(), font_path, max_text_width, max_text_height, start_size=140
    )

    accent = cfg["brand"]["colors"]["accent"]
    text_color = cfg["brand"]["colors"]["text"]
    x = int(width * 0.05)
    y = int((height - line_height * len(lines)) / 2)
    stroke_width = max(2, int(cfg["brand"]["thumbnail"]["width"] / 220))
    for i, line in enumerate(lines):
        draw.text(
            (x, y + i * line_height),
            line,
            font=font,
            fill=accent if i == 0 else text_color,
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0),
        )
    return canvas


def _render_shorts_cover(
    main_img: Image.Image,
    foreground: Optional[Image.Image],
    text: str,
    cfg: dict,
) -> Image.Image:
    width = cfg["brand"]["shorts_cover"]["width"]
    height = cfg["brand"]["shorts_cover"]["height"]
    canvas = _background_layer(main_img, foreground, width, height)
    draw = ImageDraw.Draw(canvas)

    font_path = str(ROOT / cfg["brand"]["fonts"]["heading"])
    max_text_width = int(width * 0.86)
    max_text_height = int(height * 0.3)
    font, lines, line_height = _fit_text(
        draw, text.upper(), font_path, max_text_width, max_text_height, start_size=120
    )

    accent = cfg["brand"]["colors"]["accent"]
    x = int(width * 0.07)
    y = int(height * 0.06)
    stroke_width = max(2, int(width / 220))
    for i, line in enumerate(lines):
        draw.text(
            (x, y + i * line_height),
            line,
            font=font,
            fill=accent,
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0),
        )
    return canvas


def run(
    stage3_result: dict,
    thumbnail_text_options: list,
    run_date: Optional[date] = None,
    force: bool = False,
) -> dict:
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(STAGE_NAME, run_date)
        if cached is not None:
            logger.info("stage6: using cached thumbnails")
            return cached

    cfg = load_config()
    out_dir = output_dir_for(run_date)
    thumb_dir = out_dir / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    main_img = Image.open(out_dir / stage3_result["main_image"])
    foreground = None
    if stage3_result.get("parallax"):
        foreground = Image.open(out_dir / stage3_result["parallax"]["foreground"])

    variant_count = cfg["brand"]["thumbnail"]["variant_count"]
    texts = (thumbnail_text_options or ["WHAT IS THIS?"])[:variant_count]
    while len(texts) < variant_count:
        texts.append(texts[0])

    thumbnail_paths = []
    for i, text in enumerate(texts):
        thumb = _render_thumbnail(main_img, foreground, text, cfg)
        p = thumb_dir / f"thumbnail_{i:02d}.jpg"
        thumb.convert("RGB").save(p, quality=92)
        thumbnail_paths.append({"text": text, "path": str(p.relative_to(out_dir))})
    logger.info("stage6: %d thumbnail variants rendered", len(thumbnail_paths))

    cover = _render_shorts_cover(main_img, foreground, texts[0], cfg)
    cover_path = thumb_dir / "shorts_cover.jpg"
    cover.convert("RGB").save(cover_path, quality=92)
    logger.info("stage6: Shorts cover rendered")

    result = {
        "thumbnails": thumbnail_paths,
        "shorts_cover": str(cover_path.relative_to(out_dir)),
    }
    save_stage(STAGE_NAME, result, run_date)
    logger.info("stage6: done")
    return result


if __name__ == "__main__":
    import json

    from .stage1_pick_object import run as run_stage1
    from .stage2_generate_script import run as run_stage2
    from .stage3_assets import run as run_stage3

    s1 = run_stage1()
    s2 = run_stage2(s1)
    s3 = run_stage3(s1, s2)
    result = run(s3, s2["thumbnail_text_options"], force=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
