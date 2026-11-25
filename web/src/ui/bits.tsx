import type { CSSProperties, ReactNode } from 'react';

export type Tone = 'neutral' | 'brand' | 'good' | 'warn' | 'bad';

/** Метка: значок и слово вместе, цвет только поддерживает. */
export function Chip({ tone = 'neutral', icon, title, children }: { tone?: Tone; icon?: ReactNode; title?: string; children: ReactNode }) {
  return <span className="chip" data-tone={tone} title={title}>{icon}{children}</span>;
}

/** Полоска доли. Число всегда написано рядом, поэтому полоска скрыта от читалки. */
export function Meter({ share }: { share: number }) {
  const value = Math.max(0, Math.min(1, Number.isFinite(share) ? share : 0));
  return <span className="meter" aria-hidden><i style={{ '--share': value } as CSSProperties} /></span>;
}

/** Широкая таблица прокручивается внутри себя и доступна с клавиатуры. */
export function TableScroll({ label, children }: { label: string; children: ReactNode }) {
  return <div className="table-scroll" role="region" aria-label={label} tabIndex={0}>{children}</div>;
}

export function Facts({ items }: { items: { label: string; value: ReactNode; tone?: Tone }[] }) {
  return (
    <dl className="facts">
      {items.map((item) => (
        <div key={item.label} data-tone={item.tone ?? 'neutral'}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

interface FilterBarProps<T extends string> {
  label: string; value: T; options: { value: T; label: string; count?: number }[]; onChange: (value: T) => void;
}

/** Ряд переключателей-фильтров: обычные кнопки с aria-pressed, стрелки не нужны. */
export function FilterBar<T extends string>({ label, value, options, onChange }: FilterBarProps<T>) {
  return (
    <div className="filters" role="group" aria-label={label}>
      {options.map((option) => (
        <button key={option.value} type="button" aria-pressed={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
          {option.count !== undefined && <span className="num">{option.count}</span>}
        </button>
      ))}
    </div>
  );
}
