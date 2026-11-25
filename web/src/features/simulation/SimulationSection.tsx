import { IconAlertTriangle, IconCheck } from '@tabler/icons-react';
import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useRefreshAll } from '@/api/queries';
import { isBuilding, useNodeSimulations, type SimulationRun } from '@/api/simulations';
import { BuildProgress, StageList } from './BuildProgress';
import { ScenePlayer } from './ScenePlayer';
import './simulation.css';

export const SIMULATION_ID = 'simulation';

function verdict(run: SimulationRun): string {
  if (run.state === 'cancelled') return 'Запуск остановлен.';
  return run.state === 'done' ? 'Агент закончил без сцены.' : 'Агент не достроил симулятор.';
}

/** Чем кончился последний запуск, если новой сцены после него нет. */
function Outcome({ run, hasScenes }: { run: SimulationRun; hasScenes: boolean }) {
  if (run.state === 'done' && run.is_design_only) {
    return (
      <div className="note">
        <IconCheck size={20} aria-hidden />
        <p><strong>Замысел готов.</strong> Запустите агента «до конца», и он построит сцену. <Link to="/admin/runs">Журнал</Link></p>
      </div>
    );
  }
  if (run.state === 'done' && hasScenes) return null;
  return (
    <div className="note" data-tone="warn">
      <IconAlertTriangle size={20} aria-hidden />
      <div className="sim-outcome">
        <p><strong>{verdict(run)}</strong> {run.reason} <Link to="/admin/runs">Журнал</Link></p>
        {run.state === 'failed' && <details><summary>На каком этапе</summary><StageList run={run} /></details>}
      </div>
    </div>
  );
}

/** Симулятор шага прямо на странице: готовая сцена, ход работы агента или причина отказа. */
export function SimulationSection({ chapter, node }: { chapter: string; node: string }) {
  const { data } = useNodeSimulations(chapter, node);
  const refresh = useRefreshAll();
  const run = data?.run ?? null;
  const isLive = isBuilding(run);
  const wasLive = useRef(false);
  useEffect(() => {
    if (wasLive.current && !isLive) refresh();
    wasLive.current = isLive;
  }, [isLive, refresh]);
  if (!data || (data.scenes.length === 0 && !run)) return null;
  return (
    <section className="section" aria-labelledby={SIMULATION_ID}>
      <h2 id={SIMULATION_ID} className="section-title">Симулятор</h2>
      <div className="sim-section">
        {isBuilding(run) && <BuildProgress run={run} />}
        {run && !isLive && <Outcome run={run} hasScenes={data.scenes.length > 0} />}
        {data.scenes.length > 0 && <ScenePlayer scenes={data.scenes} />}
      </div>
    </section>
  );
}
