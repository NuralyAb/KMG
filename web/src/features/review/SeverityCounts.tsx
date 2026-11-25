import { IconAlertOctagon, IconAlertTriangle, IconInfoCircle } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { SEVERITIES, type Severity } from '@/api/types';
import { SEVERITY } from '@/lib/labels';
import { Chip, type Tone } from '@/ui/bits';

export const SEVERITY_VIEW: Record<Severity, { tone: Tone; icon: ReactNode }> = {
  critical: { tone: 'bad', icon: <IconAlertOctagon size={18} aria-hidden /> },
  significant: { tone: 'warn', icon: <IconAlertTriangle size={18} aria-hidden /> },
  minor: { tone: 'neutral', icon: <IconInfoCircle size={18} aria-hidden /> },
};

export function SeverityCounts({ counts }: { counts: Record<Severity, number> }) {
  const shown = SEVERITIES.filter((s) => counts[s] > 0);
  if (shown.length === 0) return <Chip tone="good">замечаний нет</Chip>;
  return (
    <span className="chips">
      {shown.map((s) => <Chip key={s} tone={SEVERITY_VIEW[s].tone} icon={SEVERITY_VIEW[s].icon} title={SEVERITY[s]}>
        <span className="visually-hidden">{SEVERITY[s]}: </span>{counts[s]}
      </Chip>)}
    </span>
  );
}
