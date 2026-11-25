import { Tooltip } from '@mantine/core';
import type { CSSProperties } from 'react';
import { formatPercent } from '@/lib/format';

export interface Bar { key: string; name: string; value: number; detail: string }

/**
 * Горизонтальные столбики одной величины: длина несёт число, число подписано у конца, порядок по убыванию.
 * Это список: читалка слышит имя, значение и долю. Подсказка открывается и наведением, и с клавиатуры.
 */
export function BarChart({ title, bars, format }: { title: string; bars: Bar[]; format: (value: number) => string }) {
  const max = Math.max(0, ...bars.map((b) => b.value));
  const total = bars.reduce((sum, b) => sum + b.value, 0);
  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <ul>
        {bars.map((bar) => (
          <Tooltip key={bar.key} label={bar.detail} events={{ hover: true, focus: true, touch: true }} openDelay={80} position="top-start">
            <li tabIndex={0}>
              <span className="chart-name">{bar.name}</span>
              <span className="chart-plot" aria-hidden>
                <i style={{ '--share': max > 0 ? bar.value / max : 0 } as CSSProperties} />
              </span>
              <span className="chart-value num">{format(bar.value)}<span className="muted">{formatPercent(bar.value, total)}</span></span>
            </li>
          </Tooltip>
        ))}
      </ul>
    </figure>
  );
}
