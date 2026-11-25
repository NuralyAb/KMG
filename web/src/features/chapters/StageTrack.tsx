import { IconAlertTriangle, IconCheck, IconMinus } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import type { Stage, StageState } from '@/api/types';
import { formatDateTime } from '@/lib/format';
import { STAGE, STAGE_STATE, label } from '@/lib/labels';
import './chapters.css';

const ICON: Record<StageState, ReactNode> = {
  ready: <IconCheck size={14} stroke={2.6} aria-hidden />,
  stale: <IconAlertTriangle size={14} stroke={2.2} aria-hidden />,
  missing: <IconMinus size={14} stroke={2.2} aria-hidden />,
};

/** Шесть этапов одной дорожкой: значок, название и слово о состоянии. */
export function StageTrack({ stages }: { stages: Stage[] }) {
  return (
    <ol className="track" aria-label="Этапы сборки">
      {stages.map((stage) => (
        <li key={stage.name} data-state={stage.state} title={stage.updated_at ? `Обновлено ${formatDateTime(stage.updated_at)}` : 'Ещё не собирали'}>
          <span className="track-mark">{ICON[stage.state]}</span>
          <span className="track-name">{label(STAGE, stage.name)}</span>
          <span className={stage.state === 'stale' ? 'track-state' : 'visually-hidden'}>{STAGE_STATE[stage.state]}</span>
        </li>
      ))}
    </ol>
  );
}
