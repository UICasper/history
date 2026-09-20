import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Brand, ShotListItem } from "../types";

export const DataAnimation: React.FC<{
  shot: ShotListItem;
  brand: Brand;
  durationInFrames: number;
}> = ({ shot, brand, durationInFrames }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, durationInFrames], [0, 1], { extrapolateRight: "clamp" });

  if (shot.counterTarget !== undefined) {
    const value = Math.round(interpolate(p, [0, 1], [0, shot.counterTarget]));
    return (
      <AbsoluteFill
        style={{ backgroundColor: brand.background, alignItems: "center", justifyContent: "center" }}
      >
        <div style={{ fontFamily: "Anton, sans-serif", fontSize: 180, color: brand.accent }}>
          {value.toLocaleString()}
        </div>
        {shot.counterLabel && (
          <div style={{ fontFamily: "'Work Sans', sans-serif", fontSize: 36, color: brand.text, marginTop: 12 }}>
            {shot.counterLabel}
          </div>
        )}
      </AbsoluteFill>
    );
  }

  const travelX = interpolate(p, [0, 1], [8, 92]);
  return (
    <AbsoluteFill
      style={{ backgroundColor: brand.background, alignItems: "center", justifyContent: "center" }}
    >
      <div style={{ position: "relative", width: "76%", height: 4, backgroundColor: "#4a4a4a" }}>
        <div
          style={{
            position: "absolute",
            left: "8%",
            top: -6,
            width: 16,
            height: 16,
            borderRadius: 8,
            backgroundColor: brand.text,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: "92%",
            top: -6,
            width: 16,
            height: 16,
            borderRadius: 8,
            backgroundColor: brand.text,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: `${travelX}%`,
            top: -10,
            width: 24,
            height: 24,
            borderRadius: 12,
            backgroundColor: brand.accent,
            transform: "translateX(-50%)",
          }}
        />
      </div>
      {shot.counterLabel && (
        <div style={{ fontFamily: "'Work Sans', sans-serif", fontSize: 32, color: brand.text, marginTop: 28 }}>
          {shot.counterLabel}
        </div>
      )}
    </AbsoluteFill>
  );
};
