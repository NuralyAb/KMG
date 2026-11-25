import { IconChevronRight, IconListDetails } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { isActive, useChapters, useRuns, useSources } from '@/api/queries';
import type { Run } from '@/api/types';
import { formatDateTime, runDuration } from '@/lib/format';
import { COMMAND, label } from '@/lib/labels';
import { FilterBar } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { RunChip } from './RunChip';
import { RunLog } from './RunLog';
import './runs.css';

type Show = 'all' | 'active' | 'failed';

function RunItem({ run, title, isOpen, onToggle }: { run: Run; title: string; isOpen: boolean; onToggle: () => void }) {
  return (
    <li>
      <button type="button" className="run-row" aria-expanded={isOpen} onClick={onToggle}>
        <span><RunChip state={run.state} /></span>
        <span className="run-row-main"><strong>{label(COMMAND, run.command)}</strong><span className="muted">{title}</span></span>
        <span className="muted num">{formatDateTime(run.started_at)}</span>
        <span className="muted num">{run.started_at && run.finished_at ? runDuration(run.started_at, run.finished_at, 0) : ''}</span>
        <IconChevronRight size={18} aria-hidden />
      </button>
      {isOpen && (
        <div className="run-body">
          <RunLog run={run} />
          <p className="muted" style={{ marginTop: 8 }}>{run.command === 'extract'
            ? <Link to={`/admin/library/${encodeURIComponent(run.chapter)}`}>Открыть книгу</Link>
            : <Link to={`/admin/chapters/${encodeURIComponent(run.chapter)}`}>Открыть главу</Link>}</p>
        </div>
      )}
    </li>
  );
}

function RunList({ runs }: { runs: Run[] }) {
  const [params, setParams] = useSearchParams();
  const [show, setShow] = useState<Show>('all');
  const chapters = useChapters().data ?? [];
  const sources = useSources().data ?? [];
  const open = params.get('run');
  const activeId = runs.find(isActive)?.id;

  // идущий запуск раскрыт сразу, если человек ничего не выбирал
  useEffect(() => {
    if (open === null && activeId) setParams({ run: activeId }, { replace: true });
  }, [open, activeId, setParams]);

  const isShown: Record<Show, (run: Run) => boolean> = { all: () => true, active: isActive, failed: (r) => r.state === 'failed' };
  const shown = runs.filter(isShown[show]);
  return (
    <>
      <FilterBar label="Какие запуски показать" value={show} onChange={setShow} options={[
        { value: 'all', label: 'Все', count: runs.length },
        { value: 'active', label: 'Идут', count: runs.filter(isActive).length },
        { value: 'failed', label: 'С ошибкой', count: runs.filter((r) => r.state === 'failed').length },
      ]} />
      {shown.length === 0 ? <EmptyState title="Таких запусков нет" /> : (
        <ul className="run-rows" style={{ marginTop: 12 }}>
          {shown.map((run) => (
            <RunItem key={run.id} run={run} title={chapters.find((c) => c.id === run.chapter)?.title ?? sources.find((s) => s.id === run.chapter)?.name ?? run.chapter} isOpen={open === run.id}
              onToggle={() => setParams({ run: open === run.id ? '' : run.id }, { replace: true })} />
          ))}
        </ul>
      )}
    </>
  );
}

export default function RunsPage() {
  const query = useRuns();
  return (
    <>
      <PageHeader title="Запуски" docTitle="Запуски" subtitle="Одновременно идут не больше двух сборок, остальные ждут в очереди." />
      <QueryView query={query}>
        {(runs) => runs.length === 0
          ? <EmptyState icon={<IconListDetails size={32} aria-hidden />} title="Запусков ещё не было" text="Сборка запускается со страницы главы." action={<Link to="/">К списку глав</Link>} />
          : <RunList runs={runs} />}
      </QueryView>
    </>
  );
}
