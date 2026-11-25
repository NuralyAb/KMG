import { IconAlertTriangle, IconArrowLeft, IconArrowRight, IconStar } from '@tabler/icons-react';
import { useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useChapter, useNode } from '@/api/queries';
import type { RawNodeDetail } from '@/api/types';
import { counted, formatPages, FORMS } from '@/lib/format';
import { plainText } from '@/lib/formula';
import { DIFFICULTY, label } from '@/lib/labels';
import { Chip } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { RichText } from '@/ui/RichText';
import { EmptyState, ErrorState, QueryView } from '@/ui/states';
import { Picture } from '../chapter/Picture';
import { SimulationSection } from '../simulation/SimulationSection';
import { TaskView } from '../tasks/TaskView';
import { ClaimList } from './ClaimList';
import { normalizeNode, type LayerNode } from './model';
import { NodeLayers, NodeExtras } from './NodeLayers';
import { NodeAside } from './NodeAside';
import './node.css';

const nodePath = (chapter: string, node: string): string => `/admin/chapters/${encodeURIComponent(chapter)}/nodes/${encodeURIComponent(node)}`;

/** Стрелки листают шаги, если человек не печатает в поле и не держит модификатор. */
function useArrowPaging(chapter: string, prev: string | null, next: string | null): void {
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      const el = event.target;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (el instanceof Element && el.closest('input, textarea, select, video, .table-scroll, [role="tab"], [role="dialog"]')) return;
      const target = event.key === 'ArrowLeft' ? prev : event.key === 'ArrowRight' ? next : null;
      if (target) navigate(nodePath(chapter, target));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [chapter, prev, next, navigate]);
}

function Pager({ chapter, prev, next, titles }: { chapter: string; prev: string | null; next: string | null; titles: Map<string, string> }) {
  return (
    <nav className="pager" aria-label="Соседние шаги">
      {prev ? <Link to={nodePath(chapter, prev)} rel="prev"><IconArrowLeft size={18} aria-hidden /><span><span className="muted">Назад</span><RichText text={titles.get(prev) ?? prev} /></span></Link> : <span />}
      {next && <Link className="pager-next" to={nodePath(chapter, next)} rel="next"><span><span className="muted">Дальше</span><RichText text={titles.get(next) ?? next} /></span><IconArrowRight size={18} aria-hidden /></Link>}
    </nav>
  );
}

function Flags({ node }: { node: LayerNode }) {
  const { primary, secondary } = node.difficulty;
  return (
    <div className="chips">
      {node.threshold && <Chip tone="brand" icon={<IconStar aria-hidden />}>пороговая идея</Chip>}
      {[primary, secondary].filter((d): d is string => Boolean(d)).map((d) => <Chip key={d}>{label(DIFFICULTY, d)}</Chip>)}
      <Chip>стр. {formatPages(node.pages)}</Chip>
      <a href="#claims">{counted(node.claims.length, FORMS.claim)} с цитатами</a>
    </div>
  );
}

function ScanNote({ node }: { node: LayerNode }) {
  if (node.needsScan.length === 0) return null;
  return (
    <div className="note" data-tone="warn">
      <IconAlertTriangle size={20} aria-hidden />
      <div>
        <strong>Сверить со сканом</strong>
        <ul className="list">
          {node.needsScan.map((item, i) => <li key={i}>{item.page !== null && `Стр. ${item.page}. `}<RichText text={item.what} /></li>)}
        </ul>
      </div>
    </div>
  );
}

function NodeView({ chapter, detail, node }: { chapter: string; detail: RawNodeDetail; node: LayerNode }) {
  useArrowPaging(chapter, detail.prev, detail.next);
  const parent = useChapter(chapter).data;
  const titles = new Map((parent?.parts ?? []).flatMap((p) => p.nodes).map((n) => [n.id, n.short_title || n.title]));
  return (
    <>
      <PageHeader title={<RichText text={node.title} />} docTitle={plainText(node.title)}
        above={<><Link to={`/admin/chapters/${encodeURIComponent(chapter)}`}>{parent?.title ?? 'Глава'}</Link>, шаг {node.order}{titles.size > 0 && ` из ${titles.size}`}</>} />
      <div className="node-top">
        <Flags node={node} />
        <p className="muted">Тексты шага написала модель по цитатам главы. Отдельно помечены гипотезы и слова автора.</p>
        <ScanNote node={node} />
      </div>
      <div className="node">
        <div className="node-main">
          <NodeLayers node={node} />
          {detail.illustrations.length > 0 && (
            <section className="node-section" aria-label="Рисунок">
              {detail.illustrations.map((picture) => <Picture key={picture.id} picture={picture} />)}
            </section>
          )}
          <NodeExtras node={node} />
        </div>
        <NodeAside chapter={chapter} node={node} route={detail.route} titles={titles} />
      </div>
      <SimulationSection key={node.id} chapter={chapter} node={node.id} />
      <section className="section" aria-labelledby="claims">
        <div className="section-head"><h2 id="claims" className="section-title">Утверждения и цитаты</h2><span className="muted">{counted(node.claims.length, FORMS.claim)}</span></div>
        <ClaimList claims={node.claims} />
      </section>
      <section className="section" aria-labelledby="tasks">
        <h2 id="tasks">Задания</h2>
        {detail.tasks.length === 0 ? <EmptyState title="У этого шага заданий нет" />
          : <div className="tasks">{detail.tasks.map((task) => <TaskView key={task.id} task={task} chapter={chapter} />)}</div>}
      </section>
      <Pager chapter={chapter} prev={detail.prev} next={detail.next} titles={titles} />
    </>
  );
}

export default function NodePage() {
  const { id = '', nodeId = '' } = useParams();
  const query = useNode(id, nodeId);
  return (
    <QueryView query={query} rows={6}>
      {(detail) => {
        const node = normalizeNode(detail.node);
        if (!node) return <ErrorState error={new Error('Узел в layer.json не читается: нет id.')} />;
        return <NodeView chapter={id} detail={detail} node={node} />;
      }}
    </QueryView>
  );
}
