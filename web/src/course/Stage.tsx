import { useRef, useState, type ReactNode } from 'react';
import { Chip } from './bits';
import { Scene } from './Scene';
import type { Step } from './types';
import { VideoPlayer } from './VideoPlayer';

interface Slide { name: string; body: ReactNode; note?: ReactNode }

function slidesOf(s: Step, onTasks: () => void): Slide[] {
  return [
    ...s.videos.map((v, i) => ({ name: s.videos.length > 1 ? `Ролик ${i + 1}` : 'Ролик', body: <VideoPlayer video={v} />, note: <>{v.label && <><Chip>{v.label}</Chip> </>}{v.title}</> })),
    ...(s.narration ? [{ name: 'Разбор', body: <Scene step={s} narration={s.narration} onTasks={onTasks} /> }] : []),
    // содержимое этого узла рисует assets/simulation.js: контракт — data-interactive и data-params
    ...(s.interactive ? [{ name: 'Симулятор', body: <div className="screen sims" data-interactive={s.interactive.kind} data-params={JSON.stringify(s.interactive.params ?? {})} /> }] : []),
  ];
}

/** Сцена урока: только то, что движется, — ролики, озвученный разбор, симуляторы. Схема живёт в тексте. */
export function Stage({ step, onTasks }: { step: Step; onTasks: () => void }) {
  const [current, setCurrent] = useState(0);
  const slides = slidesOf(step, onTasks);
  const root = useRef<HTMLDivElement>(null);
  const show = (i: number): void => {
    setCurrent(i);
    root.current?.querySelectorAll<HTMLMediaElement>('video, audio').forEach((m) => m.pause());
  };
  if (slides.length === 0) return null;
  return (
    <div className="stage" ref={root}>
      {slides.length > 1 && (
        <div className="pills" role="group" aria-label="Что показать">
          {slides.map((x, i) => <button key={x.name} type="button" data-slide-to={i} aria-pressed={i === current} onClick={() => show(i)}>{x.name}</button>)}
        </div>
      )}
      {slides.map((x, i) => <figure key={x.name} data-slide={i} hidden={i !== current}>{x.body}{x.note && <figcaption>{x.note}</figcaption>}</figure>)}
    </div>
  );
}
