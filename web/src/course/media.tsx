import { useEffect, useState, type CSSProperties, type ReactNode, type RefObject } from 'react';
import { Icons } from './icons';

const RATES = [1, 1.25, 1.5, 2];
const STEPS = 1000;
export const clock = (t: number): string => (Number.isFinite(t) ? `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}` : '0:00');

export interface Media { isPlaying: boolean; isMuted: boolean; rate: number; now: number; total: number; toggle: () => void; mute: () => void; faster: () => void; seek: (seconds: number) => void }

/** Управление роликом или дорожкой. fallback — длина, пока браузер её не прочитал. */
export function useMedia(ref: RefObject<HTMLMediaElement | null>, fallback = 0): Media {
  const [isPlaying, setPlaying] = useState(false);
  const [isMuted, setMuted] = useState(false);
  const [rate, setRate] = useState(1);
  const [time, setTime] = useState({ now: 0, total: fallback });

  useEffect(() => {
    const media = ref.current;
    if (!media) return undefined;
    let frame = 0;
    const tick = (): void => setTime({ now: media.currentTime, total: Number.isFinite(media.duration) && media.duration > 0 ? media.duration : fallback });
    const loop = (): void => { tick(); frame = requestAnimationFrame(loop); };
    const started = (): void => { setPlaying(true); cancelAnimationFrame(frame); loop(); };
    const stopped = (): void => { setPlaying(false); cancelAnimationFrame(frame); tick(); };
    const pairs: [string, () => void][] = [['play', started], ['pause', stopped], ['ended', stopped], ['seeked', tick], ['loadedmetadata', tick], ['durationchange', tick]];
    pairs.forEach(([name, listen]) => media.addEventListener(name, listen));
    return () => { cancelAnimationFrame(frame); pairs.forEach(([name, listen]) => media.removeEventListener(name, listen)); };
  }, [ref, fallback]);
  useEffect(() => { if (ref.current) ref.current.playbackRate = rate; }, [ref, rate]);
  useEffect(() => { if (ref.current) ref.current.muted = isMuted; }, [ref, isMuted]);

  const toggle = (): void => {
    const media = ref.current;
    if (!media) return;
    if (media.paused) media.play().catch(() => { /* файл не открылся: кадр остаётся на месте */ }); else media.pause();
  };
  return {
    ...time, isPlaying, isMuted, rate, toggle, mute: () => setMuted(!isMuted), faster: () => setRate(RATES[(RATES.indexOf(rate) + 1) % RATES.length] ?? 1),
    seek: (seconds) => { if (ref.current) ref.current.currentTime = seconds; },
  };
}

export function Ctl({ name, label, onClick, pressed, children }: { name: string; label: string; onClick: () => void; pressed?: boolean; children: ReactNode }) {
  return <button type="button" className="ctl" data-stage={name} aria-label={label} aria-pressed={pressed} onClick={onClick}>{children}</button>;
}

export async function toggleFull(box: HTMLElement | null): Promise<void> {
  if (document.fullscreenElement) await document.exitFullscreen();
  else if (box?.requestFullscreen) await box.requestFullscreen();
  else (box?.querySelector('video') as HTMLVideoElement & { webkitEnterFullscreen?: () => void } | null)?.webkitEnterFullscreen?.();
}

interface ControlsProps { media: Media; what: string; captions?: boolean; onCaptions?: () => void; box: RefObject<HTMLElement | null> }

export function Controls({ media, what, captions, onCaptions, box }: ControlsProps) {
  const share = media.total ? media.now / media.total : 0;
  const speed = String(media.rate).replace('.', ',');
  return (
    <div className="controls">
      <Ctl name="play" label={media.isPlaying ? 'Пауза' : 'Смотреть'} onClick={media.toggle}>{media.isPlaying ? <Icons.pause /> : <Icons.play />}</Ctl>
      <Ctl name="mute" label={media.isMuted ? 'Включить звук' : 'Выключить звук'} onClick={media.mute}>{media.isMuted ? <Icons.mute /> : <Icons.sound />}</Ctl>
      <span className="num" data-time>{clock(media.now)}</span>
      <input type="range" min={0} max={STEPS} value={Math.round(share * STEPS)} aria-label={`Место в ${what}`} aria-valuetext={`${clock(media.now)} из ${clock(media.total)}`}
        style={{ '--share': `${share * 100}%` } as CSSProperties} onChange={(e) => media.seek((Number(e.currentTarget.value) / STEPS) * media.total)} />
      <span className="num" data-total>{clock(media.total)}</span>
      {onCaptions && <Ctl name="captions" label="Субтитры" pressed={captions} onClick={onCaptions}><Icons.captions /></Ctl>}
      <Ctl name="rate" label={`Скорость: ${speed}`} onClick={media.faster}>{speed}×</Ctl>
      <Ctl name="full" label="Во весь экран" onClick={() => void toggleFull(box.current).catch(() => { /* браузер отказал в полном экране */ })}><Icons.full /></Ctl>
    </div>
  );
}
