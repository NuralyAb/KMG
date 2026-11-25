import { Button, NativeSelect, NumberInput, Textarea, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertTriangle, IconBolt, IconCheck } from '@tabler/icons-react';
import { useState } from 'react';
import { ApiError, errorMessage } from '@/api/client';
import { useApplyFact, usePendingFact, useProbeFact, type FactPlace, type FactReport } from '@/api/fact';
import { useNode } from '@/api/queries';
import type { ChapterDetail } from '@/api/types';
import { FLAG, label } from '@/lib/labels';
import { Chip } from '@/ui/bits';
import { RichText } from '@/ui/RichText';
import { EmptyState, QueryView } from '@/ui/states';
import { claimsOf, type FactClaim } from './claims';
import './fact.css';

const PLACES = [['tasks', 'Задания'], ['pictures', 'Рисунки'], ['simulations', 'Симуляторы'], ['videos', 'Ролики']] as const;

function Places({ title, rows }: { title: string; rows: FactPlace[] }) {
  return (
    <section className="fact-place" data-hit={rows.length > 0 || undefined}>
      <h4>{title} <span className="num">{rows.length}</span></h4>
      <ul>
        {rows.map((row) => (
          <li key={row.id}><Chip tone={row.is_certain ? 'bad' : 'neutral'}>{row.is_certain ? 'старое число' : 'опирается'}</Chip> <RichText text={row.title} /></li>
        ))}
      </ul>
    </section>
  );
}

/** Цепочка: утверждение, шаги, задания, рисунки, симуляторы, ролики. */
export function Reach({ report }: { report: FactReport }) {
  return (
    <div className="fact-reach">
      {report.changes.map((change) => (
        <div key={change.claim_id} className="fact-change">
          <p><del><RichText text={change.before || '—'} /></del></p>
          <p><ins><RichText text={change.after || '—'} /></ins></p>
          {change.conflicts.length > 0 ? (
            <div className="note" data-tone={change.is_serious ? 'bad' : 'warn'}>
              <IconAlertTriangle size={20} aria-hidden />
              <div>
                <strong>Расходится с цитатой: {change.conflicts.map((f) => label(FLAG, f)).join(', ')}.</strong>
                <p>«<RichText text={change.quote} />», стр. {change.page_pdf}</p>
              </div>
            </div>
          ) : <div className="note" data-tone="good"><IconCheck size={20} aria-hidden /><div>Код расхождений с цитатой не нашёл. Смысл он не понимает, прочитайте сами.</div></div>}
        </div>
      ))}
      <div className="fact-places">
        <section className="fact-place" data-hit={report.steps.length > 0 || undefined}>
          <h4>Шаги <span className="num">{report.steps.length}</span></h4>
          <ul>{report.steps.map((s) => <li key={s.id}>{s.order}. <RichText text={s.title} /></li>)}</ul>
        </section>
        {PLACES.map(([key, title]) => <Places key={key} title={title} rows={report[key]} />)}
      </div>
      {report.replaced.length > 0 && (
        <details className="fact-replaced">
          <summary>Число заменится само: {report.replaced.length}</summary>
          <ul>{report.replaced.map((row) => <li key={row.where}><code>{row.where}</code><p><RichText text={row.after} /></p></li>)}</ul>
        </details>
      )}
      {report.tasks_hidden.length > 0 && <p>Скроются до пересоставления: {report.tasks_hidden.length}. Ответ в них считается из этого числа.</p>}
    </div>
  );
}

function Editor({ chapter, claim, onDone }: { chapter: ChapterDetail; claim: FactClaim; onDone: () => void }) {
  const [text, setText] = useState(claim.text);
  const [reason, setReason] = useState('');
  const [minutes, setMinutes] = useState<number | string>('');
  const probe = useProbeFact(chapter.id);
  const apply = useApplyFact(chapter.id);
  const report = probe.data && probe.data.changes[0]?.after === text.trim() ? probe.data : null;
  const isSerious = report?.changes.some((c) => c.is_serious) ?? false;
  const isReady = report !== null && typeof minutes === 'number' && minutes > 0 && reason.trim() !== '' && chapter.active_run === null;
  const send = (): void => {
    if (typeof minutes !== 'number') return;
    apply.mutate({ claim_id: claim.id, text: text.trim(), accept: isSerious, minutes, reason: reason.trim() }, {
      onSuccess: () => { notifications.show({ message: 'Правка записана, курс пересобирается' }); onDone(); },
    });
  };
  const error = probe.error ?? apply.error;
  return (
    <div className="fact-editor">
      <p className="muted">Цитата автора, стр. {claim.page}: «<RichText text={claim.quote} />»</p>
      <Textarea label="Новый текст" autosize minRows={2} maxLength={2000} value={text} onChange={(e) => setText(e.currentTarget.value)} />
      <Button justify="start" variant="default" leftSection={<IconBolt size={16} aria-hidden />} loading={probe.isPending}
        disabled={text.trim() === claim.text.trim() || text.trim() === ''} onClick={() => probe.mutate({ claim_id: claim.id, text: text.trim() })}>
        Показать, что заденет
      </Button>
      {error && <p className="note" data-tone="bad" role="alert">{errorMessage(error)}</p>}
      {report && (
        <>
          <Reach report={report} />
          <div className="fact-apply">
            <TextInput label="Почему правим" maxLength={300} value={reason} onChange={(e) => setReason(e.currentTarget.value)} placeholder="например, опечатка распознавания" />
            <NumberInput label="Минут потрачено" description="уйдут в журнал ручного труда" min={0.5} max={600} step={0.5} decimalSeparator="," value={minutes} onChange={setMinutes} />
            <Button color={isSerious ? 'red' : undefined} disabled={!isReady} loading={apply.isPending} onClick={send}>
              {isSerious ? 'Прав человек: записать и пересобрать' : 'Записать и пересобрать'}
            </Button>
          </div>
          {chapter.active_run !== null && <p className="muted">По главе идёт запуск: дождитесь его.</p>}
        </>
      )}
    </div>
  );
}

function Claims({ chapter, nodeId }: { chapter: ChapterDetail; nodeId: string }) {
  const query = useNode(chapter.id, nodeId);
  const [claimId, setClaimId] = useState('');
  return (
    <QueryView query={query}>
      {(detail) => {
        const claims = claimsOf(detail);
        const claim = claims.find((c) => c.id === claimId);
        return (
          <>
            <NativeSelect label="Утверждение" value={claimId} onChange={(e) => setClaimId(e.currentTarget.value)}
              data={[{ value: '', label: 'Выберите утверждение' }, ...claims.map((c) => ({ value: c.id, label: c.text.slice(0, 140) }))]} />
            {claim && <Editor key={claim.id} chapter={chapter} claim={claim} onDone={() => setClaimId('')} />}
          </>
        );
      }}
    </QueryView>
  );
}

export function FactTab({ chapter }: { chapter: ChapterDetail }) {
  const nodes = chapter.parts.flatMap((part) => part.nodes);
  const [nodeId, setNodeId] = useState('');
  const pending = usePendingFact(chapter.id);
  if (nodes.length === 0) return <EmptyState title="Слой ещё не собран" text="Править можно утверждения слоя." />;
  const isUnbuilt = pending.error instanceof ApiError && pending.error.status === 409;
  return (
    <div className="fact">
      <p className="muted">Измените одно утверждение и посмотрите, куда оно дошло: шаг, задания, рисунки, симуляторы, ролики. Пока не нажата запись, ничего не меняется.</p>
      {isUnbuilt && <p className="note" data-tone="warn">Курс ещё не собирали: сравнивать не с чем.</p>}
      {pending.data && pending.data.changes.length > 0 && (
        <section aria-labelledby="fact-pending">
          <h2 id="fact-pending" className="section-title">Ещё не дошло до курса</h2>
          <Reach report={pending.data} />
        </section>
      )}
      <NativeSelect label="Шаг" value={nodeId} onChange={(e) => setNodeId(e.currentTarget.value)}
        data={[{ value: '', label: 'Выберите шаг' }, ...nodes.map((n) => ({ value: n.id, label: `${n.order}. ${n.title}` }))]} />
      {nodeId && <Claims key={nodeId} chapter={chapter} nodeId={nodeId} />}
    </div>
  );
}
