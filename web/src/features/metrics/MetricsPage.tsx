import { NativeSelect } from '@mantine/core';
import { IconChartBar } from '@tabler/icons-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useChapters, useMetrics } from '@/api/queries';
import type { MetricRow, MetricsMeta } from '@/api/types';
import { formatInt, formatMoney, formatTokens } from '@/lib/format';
import { COMMAND, label } from '@/lib/labels';
import { Facts, FilterBar, TableScroll } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { groupRows, measureOf, totalOf, type Group, type GroupKey, type Measure } from './aggregate';
import { BarChart } from './BarChart';
import './metrics.css';

const FORMAT: Record<Measure, (value: number) => string> = { cost: formatMoney, tokens: formatTokens };
const TITLE: Record<Measure, string> = { cost: 'Стоимость по прайсу', tokens: 'Токены, вход и выход вместе' };

function GroupTable({ groups, total, nameOf, by }: { groups: Group[]; total: Group; nameOf: (key: string) => string; by: GroupKey }) {
  const row = (g: Group, name: string) => (
    <>
      <td>{name}</td><td className="right">{formatInt(g.runs)}</td><td className="right">{formatMoney(g.cost)}</td>
      <td className="right">{formatInt(g.tokensIn)}</td><td className="right">{formatInt(g.tokensOut)}</td>
      <td className="right">{formatInt(g.personMinutes + g.mentorMinutes)}</td>
    </>
  );
  return (
    <TableScroll label="Расход таблицей">
      <table className="table table-wide">
        <caption className="visually-hidden">Расход {by === 'stage' ? 'по этапам' : 'по главам'}</caption>
        <thead><tr><th>{by === 'stage' ? 'Этап' : 'Глава'}</th><th className="right">Прогонов</th><th className="right">Стоимость</th>
          <th className="right">Токены, вход</th><th className="right">Токены, выход</th><th className="right">Минуты людей</th></tr></thead>
        <tbody>{groups.map((g) => <tr key={g.key}>{row(g, nameOf(g.key))}</tr>)}</tbody>
        <tfoot><tr>{row(total, 'Всего')}</tr></tfoot>
      </table>
    </TableScroll>
  );
}

function MetricsView({ rows, meta }: { rows: MetricRow[]; meta: MetricsMeta | null }) {
  const [by, setBy] = useState<GroupKey>('stage');
  const [measure, setMeasure] = useState<Measure>('cost');
  const [chapter, setChapter] = useState('');
  const chapters = useChapters().data ?? [];
  const titleOf = (id: string): string => chapters.find((c) => c.id === id)?.title ?? id;
  const nameOf = (key: string): string => (by === 'stage' ? label(COMMAND, key) : titleOf(key));
  const ids = [...new Set(rows.map((r) => r.chapter))];
  const shown = chapter ? rows.filter((r) => r.chapter === chapter) : rows;
  const groups = groupRows(shown, by, measure);
  const total = totalOf(shown);
  return (
    <>
      <Facts items={[
        { label: 'Всего потрачено', value: formatMoney(meta?.cost_usd ?? totalOf(rows).cost) },
        { label: 'Токены, вход', value: formatTokens(meta?.tokens_in ?? totalOf(rows).tokensIn) },
        { label: 'Токены, выход', value: formatTokens(meta?.tokens_out ?? totalOf(rows).tokensOut) },
        { label: 'Прогонов', value: formatInt(rows.length) },
      ]} />
      <div className="toolbar metrics-bar">
        <FilterBar label="Разрез" value={by} onChange={setBy} options={[{ value: 'stage', label: 'По этапам' }, { value: 'chapter', label: 'По главам' }]} />
        <FilterBar label="Показатель" value={measure} onChange={setMeasure} options={[{ value: 'cost', label: 'Деньги' }, { value: 'tokens', label: 'Токены' }]} />
        {ids.length > 1 && (
          <NativeSelect className="metrics-chapter" aria-label="Глава" value={chapter} onChange={(e) => setChapter(e.currentTarget.value)}
            data={[{ value: '', label: 'Все главы' }, ...ids.map((id) => ({ value: id, label: titleOf(id) }))]} />
        )}
      </div>
      <BarChart title={`${TITLE[measure]} ${by === 'stage' ? 'по этапам' : 'по главам'}`} format={FORMAT[measure]}
        bars={groups.map((g) => ({
          key: g.key, name: nameOf(g.key), value: measureOf(g, measure),
          detail: `${formatMoney(g.cost)}, вход ${formatTokens(g.tokensIn)}, выход ${formatTokens(g.tokensOut)}, прогонов ${g.runs}`,
        }))} />
      <section className="section" aria-labelledby="table"><h2 id="table">Таблица</h2><GroupTable groups={groups} total={total} nameOf={nameOf} by={by} /></section>
    </>
  );
}

export default function MetricsPage() {
  const query = useMetrics();
  return (
    <>
      <PageHeader title="Расход" docTitle="Расход" subtitle="Деньги по прайсу модели и токены из metrics.csv. Ответы из кэша не стоят ничего." />
      <QueryView query={query}>
        {({ data, meta }) => data.length === 0
          ? <EmptyState icon={<IconChartBar size={32} aria-hidden />} title="Расхода ещё нет" text="Строки появятся после первой сборки." action={<Link to="/">К списку глав</Link>} />
          : <MetricsView rows={data} meta={meta} />}
      </QueryView>
    </>
  );
}
