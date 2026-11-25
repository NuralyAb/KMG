import { Button } from '@mantine/core';
import { IconAlertTriangle, IconShieldQuestion } from '@tabler/icons-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTrust } from '@/api/queries';
import type { AuditReport, ChapterDetail, RunCommand, Sensitivity, VerdictCounts, VerifyReport } from '@/api/types';
import { formatInt, formatPercent } from '@/lib/format';
import { DAMAGE, FLAG, label, VERDICT } from '@/lib/labels';
import { Chip, Facts, Meter, TableScroll } from '@/ui/bits';
import { RichText } from '@/ui/RichText';
import { EmptyState, QueryView } from '@/ui/states';
import { BuildDialog } from '../runs/BuildDialog';

const PAGE = 30;

function Stale() {
  return <div className="note" data-tone="warn"><IconAlertTriangle size={20} aria-hidden /><div>Слой с тех пор изменился: отчёт говорит о прежней версии. Запустите проверку ещё раз.</div></div>;
}

/** Насколько проверке можно верить: доля намеренно внесённых ошибок, которую она заметила. */
function Sense({ value, title, note }: { value: Sensitivity; title: string; note?: string }) {
  if (value.made === 0) return value.unchecked ? <p className="note" data-tone="warn">{title}: измерить не удалось, вердиктов нет ({formatInt(value.unchecked)}).</p> : null;
  return (
    <section className="trust-sense" aria-label={title}>
      <h3>{title}</h3>
      <p><strong className="num">{formatPercent(value.caught, value.made)}</strong>: замечено {formatInt(value.caught)} из {formatInt(value.made)} ошибок, внесённых намеренно.</p>
      {value.controls && value.controls.made > 0 && <p>Ложные тревоги: {formatInt(value.controls.caught)} из {formatInt(value.controls.made)} нетронутых утверждений.</p>}
      {note && <p className="muted">{note}</p>}
      {Boolean(value.unchecked) && <p>Не проверено и в замер не вошло: {formatInt(value.unchecked ?? 0)}.</p>}
      <ul>
        {Object.entries(value.kinds).map(([kind, row]) => (
          <li key={kind}><span>{label(DAMAGE, kind)}</span><Meter share={row.caught / row.made} /><span className="num">{row.caught} из {row.made}</span></li>
        ))}
      </ul>
    </section>
  );
}

function Audit({ report, chapter }: { report: AuditReport; chapter: ChapterDetail }) {
  const [limit, setLimit] = useState(PAGE);
  return (
    <>
      <Facts items={[
        { label: 'Утверждения', value: formatInt(report.claims) },
        { label: 'С расхождениями', value: formatInt(report.flagged.length), tone: report.flagged.length ? 'warn' : 'neutral' },
        { label: 'Сверить со сканом', value: formatInt(report.needs_scan), tone: report.needs_scan ? 'warn' : 'neutral' },
        { label: 'Термин раньше объяснения', value: formatInt(report.early_terms.length), tone: report.early_terms.length ? 'warn' : 'neutral' },
      ]} />
      <p className="muted trust-gap">Расхождение — повод посмотреть, а не приговор: законный пересказ тоже может отличаться от цитаты словом.</p>
      {report.sensitivity && <Sense value={report.sensitivity} title="Чутьё сверки кодом" note="Портились только утверждения без находок; порчу и проверку писали по одним правилам, поэтому это верхняя оценка." />}
      {report.flagged.length > 0 && (
        <TableScroll label="Утверждения с расхождениями">
          <table className="table table-wide">
            <thead><tr><th>Что отличается</th><th>Утверждение</th><th>Цитата</th><th className="right">Стр.</th></tr></thead>
            <tbody>
              {report.flagged.slice(0, limit).map((row) => (
                <tr key={row.claim_id}>
                  <td><span className="chips">{row.flags.map((f) => <Chip key={f} tone="warn">{label(FLAG, f)}</Chip>)}</span></td>
                  <td className="cell-text"><Link to={`/chapters/${encodeURIComponent(chapter.id)}/nodes/${encodeURIComponent(row.node_id)}`}><RichText text={row.text} /></Link></td>
                  <td className="cell-text"><RichText text={row.quote} /></td>
                  <td className="right">{row.page_pdf}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      )}
      {report.flagged.length > limit && <Button mt="md" variant="default" onClick={() => setLimit(limit + PAGE)}>Показать ещё, осталось {formatInt(report.flagged.length - limit)}</Button>}
    </>
  );
}

function Verdicts({ title, counts }: { title: string; counts: VerdictCounts }) {
  return (
    <Facts items={[
      { label: title, value: formatInt(counts.total) },
      { label: 'Следует из источника', value: formatPercent(counts.follows, counts.total) },
      { label: 'Частично', value: formatInt(counts.partial), tone: counts.partial ? 'warn' : 'neutral' },
      { label: 'В источнике нет', value: formatInt(counts.no), tone: counts.no ? 'bad' : 'neutral' },
      { label: 'Противоречит', value: formatInt(counts.contradicts), tone: counts.contradicts ? 'bad' : 'neutral' },
      { label: 'Не проверено', value: formatInt(counts.unchecked), tone: counts.unchecked ? 'warn' : 'neutral' },
    ]} />
  );
}

/** Проверяется не весь текст: остальное курс показывает как слова модели или текст книги, и это сказано прямо. */
function TextShare({ chars }: { chars: Record<string, number> }) {
  const checked = chars.checked ?? 0;
  const total = Object.values(chars).reduce((sum, n) => sum + n, 0);
  return total > 0 ? <p className="muted">На проверку ушло {formatPercent(checked, total)} связного текста. Остальное — аналогии, гипотезы, примеры и задачи книги, короткие подписи.</p> : null;
}

function Verify({ report }: { report: VerifyReport }) {
  const [limit, setLimit] = useState(PAGE);
  return (
    <>
      <p className="muted">Проверяла модель {report.checker}.</p>
      <div className="trust-facts"><Verdicts title="Утверждения" counts={report.claims} /><Verdicts title="Фразы текста" counts={report.prose} /></div>
      <TextShare chars={report.text_chars ?? {}} />
      {report.sensitivity && <Sense value={report.sensitivity} title="Чутьё проверяющей модели" />}
      {report.weak.length > 0 && (
        <TableScroll label="Что не подтвердилось">
          <table className="table table-wide">
            <thead><tr><th>Вердикт</th><th>Текст</th><th>Почему</th></tr></thead>
            <tbody>
              {report.weak.slice(0, limit).map((row) => (
                <tr key={row.id}>
                  <td className="nowrap"><Chip tone={row.verdict === 'partial' || row.verdict === 'unchecked' ? 'warn' : 'bad'}>{VERDICT[row.verdict]}</Chip></td>
                  <td className="cell-text"><RichText text={row.text} /></td>
                  <td className="cell-text">{row.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      )}
      {report.weak.length > limit && <Button mt="md" variant="default" onClick={() => setLimit(limit + PAGE)}>Показать ещё, осталось {formatInt(report.weak.length - limit)}</Button>}
    </>
  );
}

export function TrustTab({ chapter }: { chapter: ChapterDetail }) {
  const query = useTrust(chapter.id);
  const { refetch } = query;
  const run = chapter.active_run;
  const lastRun = useRef(run);
  // запуск кончился, а журнал на другой вкладке: отчёт читается заново
  useEffect(() => {
    if (lastRun.current !== null && run === null) void refetch();
    lastRun.current = run;
  }, [run, refetch]);
  const [command, setCommand] = useState<RunCommand | null>(null);
  const isBusy = chapter.active_run !== null;
  const button = (name: RunCommand, text: string) => <Button size="sm" variant="default" disabled={isBusy || chapter.counts.nodes === 0} onClick={() => setCommand(name)}>{text}</Button>;
  return (
    <>
      <QueryView query={query}>
        {(trust) => (
          <>
            <section aria-labelledby="audit">
              <div className="section-head trust-head"><h2 id="audit" className="section-title">Сверка кодом</h2>{button('audit', 'Сверить бесплатно')}</div>
              {trust.audit_stale && <Stale />}
              {trust.audit ? <div className="trust-body" data-stale={trust.audit_stale || undefined}><Audit report={trust.audit} chapter={chapter} /></div>
                : <EmptyState icon={<IconShieldQuestion size={32} aria-hidden />} title="Сверки ещё не было" text="Код сравнит каждое утверждение с его цитатой: числа, направления, отрицания, оговорки." />}
            </section>
            <section className="section" aria-labelledby="verify">
              <div className="section-head trust-head"><h2 id="verify" className="section-title">Проверка второй моделью</h2>{button('verify', 'Проверить моделью')}</div>
              {trust.verify_stale && <Stale />}
              {trust.verify ? <div className="trust-body" data-stale={trust.verify_stale || undefined}><Verify report={trust.verify} /></div>
                : <EmptyState icon={<IconShieldQuestion size={32} aria-hidden />} title="Модель ещё не проверяла" text="Без этой проверки связный текст шагов держится только на числах: следует ли он из цитат, никто не смотрел." />}
            </section>
          </>
        )}
      </QueryView>
      {command && <BuildDialog key={command} isOpen command={command} target={chapter} onClose={() => setCommand(null)} />}
    </>
  );
}
