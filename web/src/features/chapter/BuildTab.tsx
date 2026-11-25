import { Button } from '@mantine/core';
import { IconAlertTriangle, IconCheck, IconMinus } from '@tabler/icons-react';
import { useState, type ReactNode } from 'react';
import { useRuns } from '@/api/queries';
import type { ChapterDetail, Run, StageName, StageState } from '@/api/types';
import { formatDateTime } from '@/lib/format';
import { COMMAND, STAGE, STAGE_STATE, label } from '@/lib/labels';
import { Chip, type Tone } from '@/ui/bits';
import { EmptyState, QueryView } from '@/ui/states';
import { BuildDialog } from '../runs/BuildDialog';
import { RunChip } from '../runs/RunChip';
import { RunLog } from '../runs/RunLog';

const VIEW: Record<StageState, { tone: Tone; icon: ReactNode }> = {
  ready: { tone: 'good', icon: <IconCheck aria-hidden /> },
  stale: { tone: 'warn', icon: <IconAlertTriangle aria-hidden /> },
  missing: { tone: 'neutral', icon: <IconMinus aria-hidden /> },
};

const DOES: Record<StageName, string> = {
  errata: 'сверяет распознанный текст со сканом',
  layer: 'раскладывает главу на шаги с цитатами',
  routing: 'выбирает формат для каждого шага',
  tasks: 'составляет задания',
  illustrations: 'строит рисунки кодом',
  course: 'собирает страницы курса',
};

function Stages({ chapter, onStart }: { chapter: ChapterDetail; onStart: (stage: StageName) => void }) {
  const isBusy = chapter.active_run !== null;
  return (
    <ol className="stage-list">
      {chapter.stages.map((stage, i) => (
        <li key={stage.name}>
          <span className="stage-n num muted">{i + 1}</span>
          <span className="stage-name"><strong>{label(STAGE, stage.name)}</strong><span className="muted">{DOES[stage.name]}</span></span>
          <Chip tone={VIEW[stage.state].tone} icon={VIEW[stage.state].icon}>{STAGE_STATE[stage.state]}</Chip>
          <span className="stage-date muted num">{stage.updated_at ? formatDateTime(stage.updated_at) : ''}</span>
          <Button size="sm" variant={stage.state === 'stale' ? 'light' : 'default'} disabled={isBusy} onClick={() => onStart(stage.name)}
            aria-label={`${label(STAGE, stage.name)}: запустить этап`}>Запустить</Button>
        </li>
      ))}
    </ol>
  );
}

function Runs({ runs, activeId }: { runs: Run[]; activeId: string | null }) {
  const [picked, setPicked] = useState<string | null>(null);
  const current = runs.find((r) => r.id === (picked ?? activeId)) ?? runs[0];
  if (!current) return <EmptyState title="Эту главу ещё не собирали" text="Журнал появится после первого запуска." />;
  return (
    <div className="build-runs">
      <RunLog key={current.id} run={current} />
      {runs.length > 1 && (
        <ul className="run-picks" aria-label="Запуски главы">
          {runs.map((run) => (
            <li key={run.id}>
              <button type="button" aria-pressed={run.id === current.id} onClick={() => setPicked(run.id)}>
                <RunChip state={run.state} /><span>{label(COMMAND, run.command)}</span>
                <span className="muted num">{formatDateTime(run.started_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function BuildTab({ chapter }: { chapter: ChapterDetail }) {
  const query = useRuns();
  const [stage, setStage] = useState<StageName | null>(null);
  return (
    <div className="build" data-live={chapter.active_run !== null || undefined}>
      <section aria-labelledby="stages"><h2 id="stages" className="section-title">Этапы</h2><Stages chapter={chapter} onStart={setStage} /></section>
      <section aria-labelledby="log">
        <h2 id="log" className="section-title">Журнал</h2>
        <QueryView query={query} rows={3}>
          {(runs) => <Runs runs={runs.filter((r) => r.chapter === chapter.id)} activeId={chapter.active_run} />}
        </QueryView>
      </section>
      {stage && <BuildDialog key={stage} isOpen command={stage} target={chapter} onClose={() => setStage(null)} />}
    </div>
  );
}
