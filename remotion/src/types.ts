export type Chapter =
  | "quiz"
  | "reveal"
  | "how_it_was_used"
  | "similar_objects"
  | "where_it_came_from"
  | "where_it_is_now";

export type AssetType =
  | "museum_image_crop"
  | "comparison_object"
  | "code_animation";

export type Motion =
  | "parallax"
  | "spotlight"
  | "annotation"
  | "reveal"
  | "static"
  | "data_animation";

export interface ShotListItem {
  chapter: Chapter;
  duration_sec: number;
  asset_type: AssetType;
  asset_ref?: string;
  /** Art Explainer only: 0-1 fractions of the full painting the shot zooms into. */
  focus_x?: number;
  focus_y?: number;
  motion: Motion;
  notes?: string;
  /** Resolved by the Python "prepare" step to a path under public/. */
  image?: string;
  /** For parallax shots only: the background layer (foreground is `image`). */
  backgroundImage?: string;
  /** For data_animation shots: a number to count up to, if applicable. */
  counterTarget?: number;
  /** For data_animation shots: a short label, e.g. "years old". */
  counterLabel?: string;
}

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

export interface Brand {
  accent: string;
  background: string;
  text: string;
  keywordAccent: string;
}

export interface VideoProps {
  shotList: ShotListItem[];
  wordTimestamps: WordTimestamp[];
  brand: Brand;
}
