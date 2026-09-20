import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Brand, WordTimestamp } from "../types";

export const PerWordSubtitles: React.FC<{
  words: WordTimestamp[];
  brand: Brand;
}> = ({ words, brand }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  if (!words.length) return null;

  let idx = words.findIndex((w) => t >= w.start && t < w.end);
  if (idx === -1) {
    idx = words.reduce((best, w, i) => (w.start <= t ? i : best), -1);
  }
  if (idx === -1) return null;

  const windowSize = 5;
  const startIdx = Math.max(0, idx - windowSize + 1);
  const visible = words.slice(startIdx, idx + 1);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 90,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-end",
        gap: 14,
        flexWrap: "wrap",
        padding: "0 80px",
      }}
    >
      {visible.map((w, i) => {
        const isCurrent = startIdx + i === idx;
        const wordStartFrame = w.start * fps;
        const pop = interpolate(frame - wordStartFrame, [0, 6], [0.55, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <span
            key={startIdx + i}
            style={{
              fontSize: 54,
              fontWeight: 800,
              fontFamily: "'Work Sans', sans-serif",
              color: isCurrent ? brand.keywordAccent : brand.text,
              transform: `scale(${isCurrent ? pop : 1})`,
              transformOrigin: "bottom center",
              textShadow: "0 3px 10px rgba(0,0,0,0.7)",
            }}
          >
            {w.word}
          </span>
        );
      })}
    </div>
  );
};
