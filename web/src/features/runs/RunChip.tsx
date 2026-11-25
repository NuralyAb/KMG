import { IconAlertTriangle, IconCheck, IconClock, IconLoader2, IconPlayerStop } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import type { RunState } from '@/api/types';
import { RUN_STATE } from '@/lib/labels';
import { Chip, type Tone } from '@/ui/bits';
import './runs.css';

const VIEW: Record<RunState, { tone: Tone; icon: ReactNode }> = {
  queued: { tone: 'neutral', icon: <IconClock aria-hidden /> },
  running: { tone: 'brand', icon: <IconLoader2 aria-hidden className="spin" /> },
  done: { tone: 'good', icon: <IconCheck aria-hidden /> },
  failed: { tone: 'bad', icon: <IconAlertTriangle aria-hidden /> },
  cancelled: { tone: 'neutral', icon: <IconPlayerStop aria-hidden /> },
};

export function RunChip({ state }: { state: RunState }) {
  const view = VIEW[state];
  return <Chip tone={view.tone} icon={view.icon}>{RUN_STATE[state]}</Chip>;
}
