import { AbsoluteFill, Img, staticFile } from "remotion";
import { ShotListItem } from "../types";

export const StaticShot: React.FC<{ shot: ShotListItem }> = ({ shot }) => (
  <AbsoluteFill style={{ backgroundColor: "#000" }}>
    <Img
      src={staticFile(shot.image as string)}
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
  </AbsoluteFill>
);
