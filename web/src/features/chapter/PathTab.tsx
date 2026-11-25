import { IconAlertTriangle, IconRoute, IconStar } from '@tabler/icons-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { ChapterDetail, NodeRow } from '@/api/types';
import { counted, formatPages, FORMS } from '@/lib/format';
import { DIFFICULTY, label } from '@/lib/labels';
import { Chip, FilterBar } from '@/ui/bits';
import { RichText } from '@/ui/RichText';
import { EmptyState } from '@/ui/states';

type Show = 'all' | 'threshold' | 'scan';
const MATCH: Record<Show, (node: NodeRow) => boolean> = {
  all: () => true, threshold: (n) => n.threshold, scan: (n) => n.needs_scan > 0,
};

function Row({ node, chapter }: { node: NodeRow; chapter: string }) {
  const { primary, secondary } = node.difficulty;
  const difficulty = [primary, secondary].filter((d): d is string => Boolean(d)).map((d) => label(DIFFICULTY, d)).join(', ');
  return (
    <li>
      <Link className="step" to={`/admin/chapters/${encodeURIComponent(chapter)}/nodes/${encodeURIComponent(node.id)}`}>
        <span className="step-order num">{node.order}</span>
        <span className="step-main">
          <span className="step-title"><RichText text={node.title} /></span>
          <span className="muted">{difficulty}</span>
        </span>
        <span className="step-flags">
          {node.threshold && <Chip tone="brand" icon={<IconStar aria-hidden />}>порог</Chip>}
          {node.needs_scan > 0 && <Chip tone="warn" icon={<IconAlertTriangle aria-hidden />} title="Мест, которые надо сверить со сканом">скан: {node.needs_scan}</Chip>}
        </span>
        <span className="step-format muted">{node.format ?? 'без маршрута'}</span>
        <span className="step-nums muted num">
          <span>{counted(node.claims, FORMS.claim)}, {counted(node.tasks, FORMS.task)}</span>
          <span>стр. {formatPages(node.pages)}</span>
        </span>
      </Link>
    </li>
  );
}

export function PathTab({ chapter }: { chapter: ChapterDetail }) {
  const [show, setShow] = useState<Show>('all');
  const nodes = chapter.parts.flatMap((part) => part.nodes);
  if (nodes.length === 0) {
    return <EmptyState icon={<IconRoute size={32} aria-hidden />} title="Слой ещё не собран" text="Путь по главе появится после этапа «Слой»." />;
  }
  const parts = chapter.parts.map((part) => ({ ...part, nodes: part.nodes.filter(MATCH[show]) })).filter((part) => part.nodes.length > 0);
  return (
    <>
      <FilterBar label="Какие шаги показать" value={show} onChange={setShow} options={[
        { value: 'all', label: 'Все шаги', count: nodes.length },
        { value: 'threshold', label: 'Пороговые', count: nodes.filter(MATCH.threshold).length },
        { value: 'scan', label: 'Сверить со сканом', count: nodes.filter(MATCH.scan).length },
      ]} />
      {parts.length === 0 && <EmptyState title="Таких шагов нет" />}
      {parts.map((part, i) => (
        <section key={`${i}-${part.title}`} className="part" aria-label={part.title}>
          <h2><RichText text={part.title} /></h2>
          <ol className="steps">{part.nodes.map((node) => <Row key={node.id} node={node} chapter={chapter.id} />)}</ol>
        </section>
      ))}
    </>
  );
}
