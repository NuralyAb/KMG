import { Button } from '@mantine/core';
import { IconArrowsMaximize, IconArrowsMinimize, IconPlayerPlay, IconRefresh, IconX } from '@tabler/icons-react';
import { useEffect, useRef, useState, type RefObject } from 'react';
import type { Scene } from '@/api/simulations';

const FAIL_MS = 60_000;
type View = { name: 'idle' } | { name: 'loading' } | { name: 'live' } | { name: 'error'; text: string };
const IDLE: View = { name: 'idle' };

/** Сообщение проигрывателя: сцена нарисована или не открылась. */
function readMessage(data: unknown): View | null {
  if (typeof data !== 'object' || data === null || !('sim' in data)) return null;
  if (data.sim === 'ready') return { name: 'live' };
  if (data.sim === 'error') return { name: 'error', text: 'text' in data && typeof data.text === 'string' && data.text ? data.text : 'Сцена не запустилась.' };
  return null;
}

function useFullscreen() {
  const box = useRef<HTMLDivElement>(null);
  const [isFull, setFull] = useState(false);
  useEffect(() => {
    const sync = (): void => setFull(document.fullscreenElement !== null && document.fullscreenElement === box.current);
    document.addEventListener('fullscreenchange', sync);
    return () => document.removeEventListener('fullscreenchange', sync);
  }, []);
  const toggle = (): void => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void box.current?.requestFullscreen().catch(() => undefined);
  };
  return { box, isFull, toggle };
}

interface ScreenProps { scene: Scene; frame: RefObject<HTMLIFrameElement>; onView: (view: View) => void }

/** Одна сцена: обложка, загрузка и сам тренажёр на одном месте страницы. */
function Screen({ scene, frame, onView }: ScreenProps) {
  const [view, setView] = useState<View>(IDLE);
  useEffect(() => onView(view), [view, onView]);
  useEffect(() => {
    if (view.name !== 'loading') return undefined;
    const hear = (event: MessageEvent): void => {
      const next = event.source === frame.current?.contentWindow ? readMessage(event.data) : null;
      if (next) setView(next);
    };
    const timer = setTimeout(() => setView({ name: 'error', text: 'Сцена не открылась. Попробуйте ещё раз.' }), FAIL_MS);
    window.addEventListener('message', hear);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('message', hear);
    };
  }, [view.name, frame]);

  const isOpen = view.name === 'loading' || view.name === 'live';
  return (
    <div className="scene-screen" data-state={view.name}>
      {isOpen && <iframe ref={frame} title={scene.title} src={scene.player_url} allow="fullscreen" />}
      {view.name !== 'live' && scene.poster_url && <img className="scene-poster" src={scene.poster_url} alt="" />}
      {view.name === 'loading' && <div className="scene-wait" role="status"><span className="scene-spin" aria-hidden />Загружаем 3D-сцену</div>}
      {view.name === 'idle' && (
        <div className="scene-cover">
          <span className="scene-label">{scene.label}</span>
          <p>{scene.goal}</p>
          <Button variant="white" color="dark" size="md" leftSection={<IconPlayerPlay size={18} />} aria-label={`Запустить симулятор «${scene.title}»`}
            onClick={() => setView({ name: 'loading' })}>Запустить</Button>
        </div>
      )}
      {view.name === 'error' && (
        <div className="scene-cover">
          <p role="alert">{view.text}</p>
          <Button variant="white" color="dark" leftSection={<IconRefresh size={18} />} onClick={() => setView({ name: 'loading' })}>Повторить</Button>
        </div>
      )}
    </div>
  );
}

export function ScenePlayer({ scenes }: { scenes: Scene[] }) {
  const [id, setId] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  const [view, setView] = useState<View>(IDLE);
  const frame = useRef<HTMLIFrameElement>(null);
  const { box, isFull, toggle } = useFullscreen();
  const scene = scenes.find((s) => s.id === id) ?? scenes[0];
  if (!scene) return null;
  const open = (next: string): void => {
    setId(next);
    setRound((n) => n + 1);
  };
  const close = (): void => {
    if (isFull) toggle();
    open(scene.id);
  };
  return (
    <div className="scene" ref={box}>
      <div className="scene-bar">
        {scenes.length === 1 ? <strong className="scene-tabs">{scene.title}</strong> : (
          <div className="scene-tabs" role="group" aria-label="Симуляторы шага">
            {scenes.map((s) => (
              <button key={s.id} type="button" aria-pressed={s === scene} onClick={() => { if (s !== scene) open(s.id); }}>{s.title}</button>
            ))}
          </div>
        )}
        {view.name === 'live' && (
          <div className="scene-acts">
            <button type="button" onClick={() => frame.current?.contentWindow?.postMessage({ sim: 'next' }, window.location.origin)}>Новый случай</button>
            <button type="button" className="icon" aria-label={isFull ? 'Свернуть' : 'Во весь экран'} onClick={toggle}>
              {isFull ? <IconArrowsMinimize size={20} /> : <IconArrowsMaximize size={20} />}
            </button>
            <button type="button" className="icon" aria-label="Закрыть симулятор" onClick={close}><IconX size={20} /></button>
          </div>
        )}
      </div>
      <Screen key={`${scene.id}:${round}`} scene={scene} frame={frame} onView={setView} />
    </div>
  );
}
