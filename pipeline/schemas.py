from typing import List, Literal

from pydantic import BaseModel, Field

Chapter = Literal[
    "quiz",
    "reveal",
    "how_it_was_used",
    "similar_objects",
    "where_it_came_from",
    "where_it_is_now",
]

AssetType = Literal[
    "museum_image_crop",
    "comparison_object",
    "illustration",
    "code_animation",
]

Motion = Literal[
    "parallax",
    "spotlight",
    "annotation",
    "reveal",
    "static",
    "data_animation",
]


class ObjectPick(BaseModel):
    chosen_object_id: int = Field(description="The object_id of the chosen candidate")
    reason: str = Field(description="One-line reason this object is the most surprising/quiz-worthy")


class IllustrationPrompt(BaseModel):
    id: str = Field(description="Short slug, e.g. 'illus_01'")
    chapter: Chapter
    prompt: str = Field(description="Prompt for a 2D illustration image generator")


class ShotListItem(BaseModel):
    chapter: Chapter
    duration_sec: float = Field(description="3-4 seconds for most shots")
    asset_type: AssetType
    asset_ref: str = Field(
        description="Reference to the asset this shot uses: an image crop id, "
        "a comparison object id, an illustration id, or an animation name"
    )
    motion: Motion
    notes: str = ""


class VideoPackage(BaseModel):
    long_script: str = Field(description="~500-650 word spoken script for the 3-4 min long video")
    shorts_script: str = Field(description="~80-100 word spoken script for the 30-40s Short")
    illustration_prompts: List[IllustrationPrompt] = Field(
        description="8-12 prompts for 2D illustrations, consistent style/palette"
    )
    title_options: List[str] = Field(description="Exactly 3 title options")
    description: str = Field(
        description="YouTube description: first 2 lines are the hook, include timestamps, end with hashtags"
    )
    tags: str = Field(description="Comma-separated YouTube tags")
    pinned_comment: str = Field(description="Text for the creator's pinned comment")
    thumbnail_text_options: List[str] = Field(
        description="3 short (2-4 word) high-contrast hook phrases for the thumbnail, "
        "e.g. 'USED FOR WHAT?', '3000 YEARS OLD'"
    )
    shot_list: List[ShotListItem] = Field(
        description="One entry per 3-4s visual across the whole long video, in order, covering all chapters"
    )
