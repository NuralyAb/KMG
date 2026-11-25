import { RichText } from '@/ui/RichText';
import type { LayerBlock, LayerNode, TextField } from './model';

/** Помечаются исключения: гипотезы и то, что взято прямо из главы. Что остальное написала модель, сказано один раз наверху. */
function Origin({ field }: { field: { byModel: boolean; isHypothesis?: boolean } }) {
  if (field.isHypothesis) return <span className="origin">гипотеза модели</span>;
  return field.byModel ? null : <span className="origin">из главы</span>;
}

function Block({ block }: { block: LayerBlock }) {
  return (
    <section className="node-section" data-key={block.key}>
      <h3>{block.title}<Origin field={block.field} /></h3>
      <p className="prose"><RichText text={block.field.text} /></p>
    </section>
  );
}

const Paragraph = ({ field }: { field: TextField }) => <p className="prose"><RichText text={field.text} /> <Origin field={field} /></p>;

/** Слои шага: «Главное» крупнее остальных, чтобы взгляд находил суть сразу. */
export function NodeLayers({ node }: { node: LayerNode }) {
  return (
    <>
      {node.blocks.map((block) => <Block key={block.key} block={block} />)}
      {node.deeper.length > 0 && (
        <details className="more node-section">
          <summary>Глубже: {node.deeper.length}</summary>
          <div className="stack">{node.deeper.map((field, i) => <Paragraph key={i} field={field} />)}</div>
        </details>
      )}
    </>
  );
}

function Examples({ node }: { node: LayerNode }) {
  if (node.examples.length === 0) return null;
  return (
    <section className="node-section">
      <h3>Разобранные примеры автора</h3>
      <div className="stack">
        {node.examples.map((example, i) => (
          <div key={i} className="stack-tight">
            <p className="prose"><RichText text={example.condition} /></p>
            {example.steps.length > 0 && <ol className="list">{example.steps.map((step, j) => <li key={j}><RichText text={step} /></li>)}</ol>}
            {example.result && <p className="prose"><strong>Итог:</strong> <RichText text={example.result} /></p>}
            <p className="muted">{[example.page !== null && `стр. ${example.page}`, example.figure].filter(Boolean).join(', ')}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function BookTasks({ node }: { node: LayerNode }) {
  if (node.bookTasks.length === 0) return null;
  return (
    <section className="node-section">
      <h3>Задачи книги</h3>
      <ul className="plain">
        {node.bookTasks.map((task, i) => (
          <li key={i}><strong className="num">{task.number}.</strong> <RichText text={task.text} /> <span className="muted">{[task.page !== null && `стр. ${task.page}`, task.figure].filter(Boolean).join(', ')}</span></li>
        ))}
      </ul>
    </section>
  );
}

function Decision({ node }: { node: LayerNode }) {
  const { decision } = node;
  if (!decision) return null;
  return (
    <section className="node-section">
      <h3>Решение по данным</h3>
      <dl className="pairs">
        {decision.features.length > 0 && <div><dt>Признаки</dt><dd><RichText text={decision.features.join('; ')} /></dd></div>}
        <div><dt>Правило</dt><dd className="prose"><RichText text={decision.rule} /></dd></div>
        {decision.conclusion && <div><dt>Вывод</dt><dd className="prose"><RichText text={decision.conclusion} /></dd></div>}
        {decision.counterexample && <div><dt>Контрпример</dt><dd className="prose"><RichText text={decision.counterexample} /></dd></div>}
      </dl>
    </section>
  );
}

export function NodeExtras({ node }: { node: LayerNode }) {
  return (
    <>
      {node.misconception && (
        <div className="note" data-tone="bad">
          <div><strong>Заблуждение</strong> <Origin field={node.misconception} /><p className="prose"><RichText text={node.misconception.text} /></p>
            {node.misconception.ref && <p className="muted">{node.misconception.ref}</p>}</div>
        </div>
      )}
      <Decision node={node} />
      <Examples node={node} />
      <BookTasks node={node} />
      {node.dataBlocks.map((block) => <Block key={block.key} block={block} />)}
      {node.analogy && (
        <div className="note" data-tone="brand">
          <div><strong>Аналогия из ИТ</strong> <Origin field={node.analogy} /><p className="prose"><RichText text={node.analogy.text} /></p>
            {node.analogy.breaksWhere && <p className="prose"><strong>Где ломается:</strong> <RichText text={node.analogy.breaksWhere} /></p>}</div>
        </div>
      )}
      {node.lens.length > 0 && (
        <details className="more node-section">
          <summary>Где теряется время</summary>
          <dl className="pairs">{node.lens.map((row) => <div key={row.title}><dt>{row.title}</dt><dd className="prose"><RichText text={row.text} /></dd></div>)}</dl>
        </details>
      )}
    </>
  );
}
