import { Composition } from "remotion";
import { VideoProps } from "./types";
import { Video } from "./Video";
import longProps from "../sample-props/long.json";
import shortsProps from "../sample-props/shorts.json";

const FPS = 30;

function totalFrames(props: VideoProps): number {
  const totalSec = props.shotList.reduce((sum, s) => sum + s.duration_sec, 0);
  return Math.max(1, Math.round(totalSec * FPS));
}

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="LongVideo"
        component={Video}
        fps={FPS}
        width={1920}
        height={1080}
        durationInFrames={totalFrames(longProps as unknown as VideoProps)}
        defaultProps={longProps as unknown as VideoProps}
        calculateMetadata={async ({ props }) => ({
          durationInFrames: totalFrames(props as VideoProps),
        })}
      />
      <Composition
        id="Shorts"
        component={Video}
        fps={FPS}
        width={1080}
        height={1920}
        durationInFrames={totalFrames(shortsProps as unknown as VideoProps)}
        defaultProps={shortsProps as unknown as VideoProps}
        calculateMetadata={async ({ props }) => ({
          durationInFrames: totalFrames(props as VideoProps),
        })}
      />
    </>
  );
};
