import { Button } from '@mantine/core';
import { IconCube } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { RouteRow } from '@/api/types';
import { LINK_TYPE, SCORE, label } from '@/lib/labels';
import { RichText } from '@/ui/RichText';
import { BuildDialog } from '../runs/BuildDialog';
import type { LayerNode } from './model';

const MAX_SCORE = 2;

function RoutePanel({ route }: { route: RouteRow | null }) {
  if (!route) return <section><h2>Маршрут</h2><p className="muted">Формат ещё не выбран</p></section>;
  const scores = Object.entries(route.video_scores ?? {});
  const total = scores.reduce((sum, [, value]) => sum + value, 0);
  return (
    <section>
      <h2>Маршрут</h2>
      <p className="route-format">{route.format}</p>
      {route.secondary_format && route.secondary_format !== route.format && <p className="muted">запасной: {route.secondary_format}</p>}
      {scores.length > 0 && (
        <>
          <ul className="scores">
            {scores.map(([key, value]) => (
              <li key={key}>
                <span>{label(SCORE, key)}</span>
                <span className="score" role="img" aria-label={`${value} из ${MAX_SCORE}`}>
                  {Array.from({ length: MAX_SCORE }, (_, i) => <i key={i} data-on={i < value || undefined} />)}
                </span>
              </li>
            ))}
          </ul>
          <p className="muted num">видеоёмкость {total} из {scores.length * MAX_SCORE}</p>
        </>
      )}
      {route.template && <p className="muted">шаблон сцены: {route.template}</p>}
      {route.hook_short && <p className="muted">подходит для шортса-крючка</p>}
      {route.why && <p className="aside-text"><RichText text={route.why} /></p>}
    </section>
  );
}

function SimulationPanel({ chapter, node }: { chapter: string; node: LayerNode }) {
  const [isOpen, setOpen] = useState(false);
  const navigate = useNavigate();
  return (
    <section>
      <h2>Симулятор</h2>
      <p className="muted">Агент строит 3D-сцену из утверждений этого шага и проверяет её физику.</p>
      <Button variant="default" leftSection={<IconCube size={18} />} onClick={() => setOpen(true)}>Сделать симулятор</Button>
      {isOpen && (
        <BuildDialog isOpen command="simulation" target={{ id: chapter, title: node.title }} nodes={[{ id: node.id, title: node.title }]}
          onClose={() => setOpen(false)} onStarted={() => navigate('/runs')} />
      )}
    </section>
  );
}

export function NodeAside({ chapter, node, route, titles }: { chapter: string; node: LayerNode; route: RouteRow | null; titles: Map<string, string> }) {
  return (
    <aside className="node-aside" aria-label="О шаге">
      <RoutePanel route={route} />
      <SimulationPanel chapter={chapter} node={node} />
      {node.whyHere && <section><h2>Почему здесь</h2><p className="aside-text"><RichText text={node.whyHere.text} /></p></section>}
      {node.links.length > 0 && (
        <section>
          <h2>Связи</h2>
          <ul className="plain">
            {node.links.map((link, i) => (
              <li key={i}>
                <span className="muted">{label(LINK_TYPE, link.type)}: </span>
                {titles.has(link.target)
                  ? <Link to={`/chapters/${encodeURIComponent(chapter)}/nodes/${encodeURIComponent(link.target)}`}><RichText text={titles.get(link.target) ?? link.target} /></Link>
                  : <span className="anywhere">{link.target}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {node.glossary.length > 0 && (
        <section>
          <h2>Термины</h2>
          <dl className="terms">{node.glossary.map((g) => <div key={g.term}><dt><RichText text={g.term} /></dt><dd><RichText text={g.definition} /></dd></div>)}</dl>
        </section>
      )}
    </aside>
  );
}
