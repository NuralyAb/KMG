import { Button } from '@mantine/core';
import { IconPlayerStop } from '@tabler/icons-react';
import { useEffect, useRef, useState } from 'react';
import { isActive, useCancelRun, useRefreshAll } from '@/api/queries';
import { errorMessage } from '@/api/client';
import type { Run } from '@/api/types';
import { formatDateTime, runDuration } from '@/lib/format';
import { COMMAND, label } from '@/lib/labels';
import { RunChip } from './RunChip';
import { useRunEvents, type Connection } from './useRunEvents';
import './runs.css';

const NEAR_BOTTOM_PX = 24;
const TICK_MS = 1_000;

const CONNECTION: Partial<Record<Connection, string>> = {
  connecting: 'Подключение к журналу', lost: 'Связь потеряна, подключаюсь снова', closed: '',
};

/** Секундомер идёт только пока запуск идёт. */
function useNow(isTicking: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!isTicking) return undefined;
    const id = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(id);
  }, [isTicking]);
  return now;
}

/** Журнал следует за последней строкой, пока человек сам не прокрутил вверх. */
function LogView({ lines }: { lines: string[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [isFollowing, setFollowing] = useState(true);
  useEffect(() => {
    if (isFollowing && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines, isFollowing]);
  return (
    <div className="log-wrap">
      <div className="log" role="log" aria-label="Журнал запуска" tabIndex={0} ref={box}
        onScroll={(e) => {
          const el = e.currentTarget;
          setFollowing(el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX);
        }}>
        {lines.length === 0 ? <span className="muted">Журнал пока пуст</span> : lines.map((line, i) => <div key={i}>{line || ' '}</div>)}
      </div>
      {!isFollowing && <Button className="log-follow" size="xs" variant="default" onClick={() => setFollowing(true)}>К последней строке</Button>}
    </div>
  );
}

/** Запуск целиком: команда, состояние, время, журнал вживую, отмена. Завершённый показывает сохранённый хвост. */
export function RunLog({ run }: { run: Run }) {
  const refresh = useRefreshAll();
  // поток нужен и завершённому запуску: сервер отдаёт по нему полный журнал
  const events = useRunEvents(run.id, refresh);
  const cancel = useCancelRun();
  const state = events.state ?? run.state;
  const isLive = isActive({ state });
  const now = useNow(isLive);
  const lines = events.lines.length ? events.lines : run.log_tail;
  const code = events.exitCode ?? run.exit_code;
  const note = isLive ? CONNECTION[events.connection] : '';
  return (
    <section className="run-panel" aria-label={`Запуск: ${label(COMMAND, run.command)}`}>
      <div className="run-panel-head">
        <strong>{label(COMMAND, run.command)}</strong>
        <RunChip state={state} />
        <span className="muted num">{formatDateTime(run.started_at)}</span>
        <span className="muted num">{runDuration(run.started_at, isLive ? null : run.finished_at, now)}</span>
        {state === 'failed' && code !== null && <span className="muted">код {code}</span>}
        {note && <span className="muted" role="status">{note}</span>}
        {isLive && (
          <Button className="run-cancel" size="sm" variant="default" leftSection={<IconPlayerStop size={16} />}
            loading={cancel.isPending} onClick={() => cancel.mutate(run.id)}>Остановить</Button>
        )}
      </div>
      {cancel.isError && <p role="alert" className="text-bad">{errorMessage(cancel.error)}</p>}
      <LogView lines={lines} />
    </section>
  );
}
