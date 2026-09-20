import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ShotListItem } from "../types";

export const Reveal: React.FC<{
  shot: ShotListItem;
  durationInFrames: number;
}> = ({ shot, durationInFrames }) => {
  const frame = useCurrentFrame();
  const lit = interpolate(frame, [0, Math.max(1, durationInFrames * 0.4)], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Img
        src={staticFile(shot.image as string)}
        style={{ width: "100%", height: "100%", objectFit: "cover", filter: `brightness(${lit})` }}
      />
    </AbsoluteFill>
  );
};
