import { Brand, ShotListItem } from "../types";
import { Annotation } from "./Annotation";
import { DataAnimation } from "./DataAnimation";
import { Parallax } from "./Parallax";
import { Reveal } from "./Reveal";
import { Spotlight } from "./Spotlight";
import { StaticShot } from "./StaticShot";

export const Shot: React.FC<{
  shot: ShotListItem;
  brand: Brand;
  durationInFrames: number;
}> = ({ shot, brand, durationInFrames }) => {
  switch (shot.motion) {
    case "parallax":
      return <Parallax shot={shot} durationInFrames={durationInFrames} />;
    case "spotlight":
      return <Spotlight shot={shot} durationInFrames={durationInFrames} />;
    case "annotation":
      return <Annotation shot={shot} brand={brand} durationInFrames={durationInFrames} />;
    case "reveal":
      return <Reveal shot={shot} durationInFrames={durationInFrames} />;
    case "data_animation":
      return <DataAnimation shot={shot} brand={brand} durationInFrames={durationInFrames} />;
    default:
      return <StaticShot shot={shot} />;
  }
};
