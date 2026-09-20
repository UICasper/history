import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { PerWordSubtitles } from "./components/PerWordSubtitles";
import { Shot } from "./components/Shot";
import { VideoProps } from "./types";

// Audio (voice/music/chapter SFX) is intentionally NOT rendered here. Remotion's
// bundled ffprobe is used to inspect any <Audio> source, and on some machines
// (observed: Windows with Smart App Control enforcing) that bundled binary is
// blocked by OS policy. Audio is muxed on afterwards with the system ffmpeg in
// stage5_render.py instead, which sidesteps the bundled binary entirely.
export const Video: React.FC<VideoProps> = ({ shotList, wordTimestamps, brand }) => {
  const { fps } = useVideoConfig();
  let frameCursor = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: brand.background }}>
      {shotList.map((shot, i) => {
        const durationInFrames = Math.max(1, Math.round(shot.duration_sec * fps));
        const from = frameCursor;
        frameCursor += durationInFrames;
        return (
          <Sequence key={i} from={from} durationInFrames={durationInFrames}>
            <Shot shot={shot} brand={brand} durationInFrames={durationInFrames} />
          </Sequence>
        );
      })}
      <PerWordSubtitles words={wordTimestamps} brand={brand} />
    </AbsoluteFill>
  );
};
