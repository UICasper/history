import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Brand, ShotListItem } from "../types";

export const Annotation: React.FC<{
  shot: ShotListItem;
  brand: Brand;
  durationInFrames: number;
}> = ({ shot, brand, durationInFrames }) => {
  const frame = useCurrentFrame();
  const draw = interpolate(frame, [4, Math.max(8, Math.min(24, durationInFrames * 0.6))], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cx = 62;
  const cy = 40;
  const r = 16;
  const circumference = 2 * Math.PI * r;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Img src={staticFile(shot.image as string)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      <svg
        viewBox="0 0 100 56.25"
        preserveAspectRatio="none"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      >
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={brand.accent}
          strokeWidth={1.4}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - draw)}
        />
      </svg>
    </AbsoluteFill>
  );
};
