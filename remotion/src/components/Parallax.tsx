import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ShotListItem } from "../types";

export const Parallax: React.FC<{
  shot: ShotListItem;
  durationInFrames: number;
}> = ({ shot, durationInFrames }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, durationInFrames], [0, 1]);
  const bgShift = interpolate(p, [0, 1], [-2, 2]);
  const fgShift = interpolate(p, [0, 1], [-6, 6]);

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#000" }}>
      {shot.backgroundImage && (
        <Img
          src={staticFile(shot.backgroundImage)}
          style={{
            position: "absolute",
            width: "112%",
            height: "112%",
            left: `${-6 + bgShift}%`,
            top: "-6%",
            objectFit: "cover",
            filter: "brightness(0.7) blur(1px)",
          }}
        />
      )}
      {shot.image && (
        <Img
          src={staticFile(shot.image)}
          style={{
            position: "absolute",
            width: "120%",
            height: "120%",
            left: `${-10 + fgShift}%`,
            top: "-10%",
            objectFit: "contain",
          }}
        />
      )}
    </AbsoluteFill>
  );
};
