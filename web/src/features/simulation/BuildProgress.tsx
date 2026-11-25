import { Button } from '@mantine/core';
import { IconPlayerStop } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { errorMessage } from '@/api/client';
import { useCancelRun } from '@/api/queries';
import type { SimulationRun, StageName } from '@/api/simulations';
import { runDuration } from '@/lib/format';
import { Meter } from '@/ui/bits';

const STAGE: Record<StageName, string> = {
  facts: 'Берёт факты шага из книги', design: 'Придумывает задачу', model: 'Считает физику', scene: 'Строит 3D-сцену', game: 'Составляет задание',
  look: 'Смотрит кадры и исправляет', finish: 'Проходит сам от начала до конца', course: 'Ставит в курс',
};
const TICK_MS = 1_000;

function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(id);
  }, []);
  return now;
}

function headline(run: SimulationRun): string {
  if (run.state === 'queued') return 'Запуск ждёт очереди';
  return run.is_design_only ? 'ИИ-агент придумывает симулятор' : 'ИИ-агент строит симулятор';
}

export function StageList({ run }: { run: SimulationRun }) {
  return (
    <ol className="sim-stages">
      {run.stages.map((s) => <li key={s.name} data-state={s.state} aria-current={s.state === 'now' ? 'step' : undefined}>{STAGE[s.name]}</li>)}
    </ol>
  );
}

/** Агент работает: что готово, что идёт, сколько прошло. */
export function BuildProgress({ run }: { run: SimulationRun }) {
  const now = useNow();
  const cancel = useCancelRun();
  const done = run.stages.filter((s) => s.state === 'done').length;
  const current = run.stages.filter((s) => s.state === 'now').map((s) => STAGE[s.name]).join(', ');
  return (
    <div className="sim-build">
      <div className="sim-build-head">
        <span className="scene-spin" aria-hidden />
        <strong>{headline(run)}</strong>
        <span className="muted num">{runDuration(run.started_at, null, now)}</span>
        <Button size="sm" variant="default" leftSection={<IconPlayerStop size={16} />} loading={cancel.isPending} onClick={() => cancel.mutate(run.id)}>Остановить</Button>
      </div>
      <Meter share={done / run.stages.length} />
      <StageList run={run} />
      <p className="muted">
        {run.retry > 0 && `Проверка нашла ошибки, агент исправляет, попытка ${run.retry}. `}
        {run.is_design_only ? 'Обычно это 1–2 минуты.' : 'Обычно это 5–15 минут. Со страницы можно уйти: сцена появится здесь сама.'}
      </p>
      <p className="sim-said" role="status">{current && `Сейчас: ${current}. Готово ${done} из ${run.stages.length}`}</p>
      {cancel.isError && <p role="alert" className="text-bad">{errorMessage(cancel.error)}</p>}
    </div>
  );
}
