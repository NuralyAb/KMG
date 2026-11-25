import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useCourse } from './context';
import { markTerms } from './core';
import { Icons } from './icons';
import { clock, Controls, useMedia, type Media } from './media';
import type { Beat, Narration, Picture, Step } from './types';

const LINE_GAP = 36;
/** Доля схемы, которая видна уже на заставке: оси и первый блок. */
const FIRST = 0.12;

/** Части схемы по порядку рисования; строки одной подписи появляются вместе. Фон холста виден всегда. */
function groupsOf(svg: SVGSVGElement): SVGElement[][] {
  const parts = [...svg.children].filter((x): x is SVGElement => x instanceof SVGElement && x.tagName !== 'defs');
  const isBack = (x: SVGElement): boolean => x.tagName === 'rect' && x.getAttribute('width') === svg.getAttribute('width') && x.getAttribute('height') === svg.getAttribute('height');
  let lastText = -Infinity;
  return parts.filter((x) => !isBack(x) || x.getAttribute('stroke') !== 'none').reduce<SVGElement[][]>((groups, part) => {
    const last = groups.at(-1);
    if (part.tagName !== 'text') { lastText = -Infinity; return [...groups, [part]]; }
    const y = Number(part.getAttribute('y'));
    const isSame = last !== undefined && (lastText === -Infinity || Math.abs(y - lastText) < LINE_GAP);
    lastText = y;
    return isSame && last ? [...groups.slice(0, -1), [...last, part]] : [...groups, [part]];
  }, []);
}

/** Схема урока, которая проступает по ходу рассказа. Разметку проверил build.py: только рисующие теги. */
function Drawing({ picture, share }: { picture: Picture; share: number }) {
  const root = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const svg = root.current?.querySelector('svg');
    if (!svg) return;
    const groups = groupsOf(svg);
    const visible = Math.ceil(groups.length * share);
    groups.forEach((group, i) => group.forEach((part) => part.classList.toggle('off', i >= visible)));
  }, [share, picture]);
  return <div className="scene-drawing" role="img" aria-label={picture.alt} ref={root} dangerouslySetInnerHTML={{ __html: picture.svg ?? '' }} />;
}

const beatAt = (beats: Beat[], now: number): number => Math.max(0, beats.filter((b) => now >= b.start).length - 1);

/** Фраза крупно: слова зажигаются вслед за голосом, термин — отдельной меткой. */
function Phrase({ beat, now, step }: { beat: Beat; now: number; step: Step }) {
  const words = beat.text.split(/\s+/);
  const said = Math.ceil(Math.min(1, Math.max(0, (now - beat.start) / Math.max(0.1, beat.end - beat.start - 0.6))) * words.length);
  const terms = useMemo(() => {
    const marks = markTerms([beat.text], step.glossary)[0] ?? '';
    return step.glossary.filter((_, i) => marks.includes(String.fromCharCode(0xE100 + i)));
  }, [beat, step]);
  const size = beat.text.length > 150 ? ' long' : beat.text.length < 60 ? ' brief' : '';
  return (
    <>
      <p className={`scene-phrase${size}`} key={beat.start}>{words.map((w, i) => <span key={i} className={i < said ? 'said' : undefined}>{w} </span>)}</p>
      {terms[0] && <p className="scene-term" key={terms[0].term}>{terms[0].term}</p>}
    </>
  );
}

/** Расшифровка под видео: фраза, которая звучит, подсвечена; нажатие перематывает к ней. */
function Transcript({ beats, media, index }: { beats: Beat[]; media: Media; index: number }) {
  const root = useRef<HTMLOListElement>(null);
  const [isFollowing, setFollowing] = useState(true);
  useEffect(() => {
    const box = root.current;
    const row = box?.querySelector<HTMLElement>('[aria-current]');
    if (!box || !row || !isFollowing || !media.isPlaying) return;
    box.scrollTo?.({ top: row.offsetTop - box.clientHeight / 3, behavior: 'smooth' });
  }, [index, isFollowing, media.isPlaying]);
  return (
    <ol className="transcript" ref={root} onWheel={() => setFollowing(false)} onTouchMove={() => setFollowing(false)}>
      {beats.map((b, i) => (
        <li key={b.start} aria-current={i === index && media.now > 0 ? 'true' : undefined}>
          <button type="button" onClick={() => { media.seek(b.start + 0.01); setFollowing(true); if (!media.isPlaying) media.toggle(); }}>
            <span className="num time">{clock(b.start)}</span><span>{b.text}</span>{b.page && <span className="page">стр.&nbsp;{b.page}</span>}
          </button>
        </li>
      ))}
    </ol>
  );
}

/** Озвученный разбор: не ролик, а живая сцена — дорожка, фразы слоя и схема урока. Под ней — расшифровка. */
export function Scene({ step, narration, onDone }: { step: Step; narration: Narration; onDone: () => void }) {
  const { num, course } = useCourse();
  const box = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLAudioElement>(null);
  const media = useMedia(ref, narration.duration);
  const [hasCaptions, setCaptions] = useState(false);
  const [isLost, setLost] = useState(false);
  const { beats } = narration;
  const index = beatAt(beats, media.now);
  const beat = beats[index];
  const picture = step.pictures.find((p) => p.svg);
  const isStart = media.now === 0 && !media.isPlaying;
  const isEnd = !media.isPlaying && media.now > 0 && media.now >= media.total - 0.2;
  const part = course.parts.find((p) => p.nodes.includes(step.id));
  const share = isStart || isEnd ? 1 : Math.min(1, FIRST + (1 - FIRST) * ((index + 1) / beats.length));
  if (!beat) return null;
  return (
    <div className="talk">
      <div className={`screen scene${picture ? '' : ' plain'}${media.isPlaying ? ' playing' : ''}`} data-scene data-state={isStart ? 'start' : isEnd ? 'end' : 'on'} ref={box}>
        <audio ref={ref} preload="metadata" src={narration.audio} onError={() => setLost(true)} />
        <div className="scene-frame" onClick={media.toggle}>
          <div className="scene-text">
            <p className="scene-head"><span className="scene-num">{num(step)}</span>{part?.title}</p>
            {isStart && <><p className="scene-title">{step.short_title}</p><p className="scene-play">{isLost ? 'Озвучка не загрузилась: рядом с index.html нужна папка narration' : <><span><Icons.play /></span>Смотреть разбор, {clock(narration.duration)}</>}</p></>}
            {isEnd && <><p className="scene-title">Разбор окончен</p><button type="button" className="scene-go" onClick={(e) => { e.stopPropagation(); onDone(); }}>Дальше<Icons.right /></button></>}
            {!isStart && !isEnd && (beat.kind === 'title' ? <p className="scene-title">{beat.text}</p> : <Phrase beat={beat} now={media.now} step={step} />)}
          </div>
          {picture && <div className="scene-side"><Drawing picture={picture} share={share} /></div>}
          <p className="scene-mark"><span>{picture ? picture.label : 'схема'}</span>{beat.page && !isStart && !isEnd ? <span>стр. {beat.page}</span> : <span>пересказ модели</span>}</p>
        </div>
        {hasCaptions && !isStart && !isEnd && <p className="scene-captions">{beat.text}</p>}
        <Controls media={media} what="разборе" box={box} captions={hasCaptions} onCaptions={() => setCaptions(!hasCaptions)} />
      </div>
      <section className="under" aria-label="Расшифровка">
        <div className="under-head"><h2>Расшифровка</h2><a className="link" href={narration.audio} download>Скачать звук</a></div>
        <Transcript beats={beats} media={media} index={index} />
      </section>
    </div>
  );
}
