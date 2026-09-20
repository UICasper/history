import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ShotListItem } from "../types";

export const Spotlight: React.FC<{
  shot: ShotListItem;
  durationInFrames: number;
}> = ({ shot, durationInFrames }) => {
  const frame = useCurrentFrame();
  const grow = interpolate(frame, [0, Math.max(1, durationInFrames * 0.5)], [0, 1], {
    extrapolateRight: "clamp",
  });
  const radius = interpolate(grow, [0, 1], [10, 34]);
  const cx = 50;
  const cy = 45;
  const mask = `radial-gradient(circle at ${cx}% ${cy}%, black ${radius}%, transparent ${radius + 12}%)`;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Img
        src={staticFile(shot.image as string)}
        style={{ width: "100%", height: "100%", objectFit: "cover", filter: "brightness(0.32)" }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          WebkitMaskImage: mask,
          maskImage: mask,
        }}
      >
        <Img src={staticFile(shot.image as string)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
    </AbsoluteFill>
  );
};
