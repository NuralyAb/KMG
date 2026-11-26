import { Fragment, useLayoutEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { useCourse } from './context';

/** Текст слоя: всё экранирует core.ts, разметкой становятся только формулы, индексы и термины. */
export function Rich({ text }: { text: unknown }) {
  const { rich } = useCourse();
  return <span dangerouslySetInnerHTML={{ __html: rich(text) }} />;
}

/** Готовая разметка из core.ts (формула, обозначение). */
export const Html = ({ html }: { html: string }) => <span dangerouslySetInnerHTML={{ __html: html }} />;

export function Pages({ list }: { list?: number[] | null }) {
  if (!list?.length) return null;
  return <> <span className="page">стр.&nbsp;{list.join(', ')}</span></>;
}

export const Chip = ({ children }: { children: ReactNode }) => <> <span className="chip">{children}</span></>;

const WHO = { author: 'автор', model: 'модель' } as const;
export type Who = keyof typeof WHO;
export const WhoChip = ({ who }: { who: Who }) => <span className={`chip who ${who}`}>{WHO[who]}</span>;

export const Bar = ({ share }: { share: number }) => <span className="progress" aria-hidden><i style={{ width: `${share}%` } as CSSProperties} /></span>;

/** Кольцо прогресса, как в шапке больших площадок: доля пройденного по окружности. */
export function Ring({ share, size = 36 }: { share: number; size?: number }) {
  const r = 15.5;
  const length = 2 * Math.PI * r;
  return (
    <svg className="ring" viewBox="0 0 36 36" width={size} height={size} aria-hidden>
      <circle className="ring-track" cx="18" cy="18" r={r} />
      {share > 0 && <circle className="ring-fill" cx="18" cy="18" r={r} strokeDasharray={`${(length * share) / 100} ${length}`} transform="rotate(-90 18 18)" />}
    </svg>
  );
}

export function Items<T>({ list, children, as: Tag = 'ul', className }: { list?: T[] | null; children: (x: T, i: number) => ReactNode; as?: 'ul' | 'ol'; className?: string }) {
  if (!list?.length) return null;
  return <Tag className={className}>{list.map((x, i) => <Fragment key={i}>{children(x, i)}</Fragment>)}</Tag>;
}

/** React 18 не знает inert: атрибут ставится сам. */
export function useInert<T extends HTMLElement>(on: boolean) {
  const ref = useRef<T>(null);
  useLayoutEffect(() => { ref.current?.toggleAttribute('inert', on); }, [on]);
  return ref;
}
