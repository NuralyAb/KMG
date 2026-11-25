import { useEffect, useRef, useState } from 'react';
import { apiPath } from '@/api/client';
import type { RunState } from '@/api/types';

export const LOG_LIMIT = 2_000;
const FINAL: ReadonlySet<string> = new Set(['done', 'failed', 'cancelled']);
const STATES: ReadonlySet<string> = new Set(['queued', 'running', 'done', 'failed', 'cancelled']);

export type Connection = 'idle' | 'connecting' | 'open' | 'lost' | 'closed';
export interface RunEvents { lines: string[]; state: RunState | null; exitCode: number | null; connection: Connection }

const START: RunEvents = { lines: [], state: null, exitCode: null, connection: 'idle' };

function parse(data: unknown): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(String(data));
    return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/** Журнал хранит последние строки: длинная сборка не должна съедать память вкладки. */
export function appendLine(lines: string[], line: string): string[] {
  return [...lines.slice(Math.max(0, lines.length - LOG_LIMIT + 1)), line];
}

/**
 * Живой журнал запуска. При каждом подключении сервер отдаёт накопленный журнал заново,
 * поэтому на `open` строки сбрасываются. После конечного состояния поток закрывается, иначе EventSource переподключится.
 */
export function useRunEvents(runId: string | null, onFinish?: () => void): RunEvents {
  const [events, setEvents] = useState<RunEvents>(START);
  const finish = useRef(onFinish);
  useEffect(() => {
    finish.current = onFinish;
  }, [onFinish]);

  useEffect(() => {
    if (!runId) {
      setEvents(START);
      return undefined;
    }
    setEvents({ ...START, connection: 'connecting' });
    const source = new EventSource(apiPath(['runs', runId, 'events']));
    source.onopen = () => setEvents((prev) => ({ ...prev, lines: [], connection: 'open' }));
    source.onerror = () => setEvents((prev) => ({ ...prev, connection: source.readyState === EventSource.CLOSED ? 'closed' : 'lost' }));
    source.addEventListener('log', (event) => {
      const { line } = parse((event as MessageEvent).data);
      if (typeof line === 'string') setEvents((prev) => ({ ...prev, lines: appendLine(prev.lines, line) }));
    });
    source.addEventListener('state', (event) => {
      const { state, exit_code: code } = parse((event as MessageEvent).data);
      if (typeof state !== 'string' || !STATES.has(state)) return;
      const isFinal = FINAL.has(state);
      setEvents((prev) => ({
        ...prev, state: state as RunState, exitCode: typeof code === 'number' ? code : null, connection: isFinal ? 'closed' : prev.connection,
      }));
      if (isFinal) {
        source.close();
        finish.current?.();
      }
    });
    return () => source.close();
  }, [runId]);

  return events;
}
