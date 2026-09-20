import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Brand, WordTimestamp } from "../types";

export const PerWordSubtitles: React.FC<{
  words: WordTimestamp[];
  brand: Brand;
}> = ({ words, brand }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const t = frame / fps;

  if (!words.length) return null;

  const idx = words.findIndex((w) => t >= w.start && t < w.end);
  if (idx === -1) return null;

  const word = words[idx];
  const wordStartFrame = word.start * fps;
  const wordEndFrame = word.end * fps;

  const pop = interpolate(frame - wordStartFrame, [0, 4, 8], [0.5, 1.12, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [wordEndFrame - 3, wordEndFrame],
    [1, 0.85],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        top: "68%",
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 80px",
      }}
    >
      <span
        key={idx}
        style={{
          fontSize: Math.round(width * 0.075),
          fontWeight: 800,
          fontFamily: "'Work Sans', sans-serif",
          color: brand.text,
          WebkitTextStroke: `${Math.max(2, Math.round(width * 0.003))}px ${brand.background}`,
          textShadow: `0 0 ${Math.round(width * 0.02)}px ${brand.keywordAccent}99, 0 6px 14px rgba(0,0,0,0.65)`,
          transform: `scale(${pop})`,
          opacity: fadeOut,
          whiteSpace: "nowrap",
        }}
      >
        {word.word}
      </span>
    </div>
  );
};
