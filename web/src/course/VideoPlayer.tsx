import { useEffect, useMemo, useRef, useState } from 'react';
import { Controls, useMedia } from './media';
import type { Video } from './types';

/** Верх субтитров, доля высоты кадра в процентах. */
const LIFT = 84;

export function VideoPlayer({ video }: { video: Video }) {
  const box = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLVideoElement>(null);
  const lines = useRef<HTMLTrackElement>(null);
  const media = useMedia(ref);
  const [hasCaptions, setCaptions] = useState(true);
  // соседний .vtt с file:// не читается, поэтому текст субтитров лежит в data.js
  const track = useMemo(() => (video.vtt ? URL.createObjectURL(new Blob([video.vtt], { type: 'text/vtt' })) : video.subtitles ?? ''), [video]);
  useEffect(() => () => { if (track.startsWith('blob:')) URL.revokeObjectURL(track); }, [track]);
  // субтитры поднимаются над панелью управления; событие load у track React не слушает
  useEffect(() => {
    const el = lines.current;
    const lift = (): void => [...el?.track.cues ?? []].forEach((cue) => { if (cue instanceof VTTCue) { cue.snapToLines = false; cue.line = LIFT; } });
    el?.addEventListener('load', lift);
    return () => el?.removeEventListener('load', lift);
  }, [track]);
  useEffect(() => { const text = ref.current?.textTracks[0]; if (text) text.mode = hasCaptions ? 'showing' : 'hidden'; }, [hasCaptions, track]);
  return (
    <div className={`screen${video.format === '9:16' || video.format === 'short' ? ' tall' : ''}${media.isPlaying ? ' playing' : ''}`} data-video ref={box}>
      <video ref={ref} preload="metadata" playsInline src={video.src} aria-label={video.title} onClick={media.toggle}>
        {track && <track kind="subtitles" srcLang="ru" label="Русские" default src={track} ref={lines} />}
      </video>
      <Controls media={media} what="ролике" box={box} captions={hasCaptions} onCaptions={track ? () => setCaptions(!hasCaptions) : undefined} />
    </div>
  );
}
