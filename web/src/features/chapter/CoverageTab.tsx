import { Button } from '@mantine/core';
import { IconChecklist } from '@tabler/icons-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useCoverage } from '@/api/queries';
import type { ChapterDetail, CoverageRow } from '@/api/types';
import { formatInt, formatPercent } from '@/lib/format';
import { UNIT_KIND, label } from '@/lib/labels';
import { FilterBar, Meter, TableScroll } from '@/ui/bits';
import { RichText } from '@/ui/RichText';
import { EmptyState, QueryView } from '@/ui/states';

const PAGE = 100;

function Rows({ rows, chapter }: { rows: CoverageRow[]; chapter: ChapterDetail }) {
  const [limit, setLimit] = useState(PAGE);
  const titles = new Map(chapter.parts.flatMap((p) => p.nodes).map((n) => [n.id, n.short_title || n.title]));
  return (
    <>
      <TableScroll label="Таблица покрытия главы">
        <table className="table table-wide">
          <thead><tr><th>Единица</th><th>Вид</th><th className="right">Стр.</th><th>Начало</th><th>Где в курсе</th></tr></thead>
          <tbody>
            {rows.slice(0, limit).map((row) => (
              <tr key={row.unit_id}>
                <td className="nowrap">{row.unit_id}</td>
                <td className="nowrap">{label(UNIT_KIND, row.kind)}</td>
                <td className="right">{row.page_pdf}</td>
                <td className="cell-text"><RichText text={row.excerpt} /></td>
                <td className="cell-text">
                  {row.node_ids.length > 0
                    ? <ul className="plain">{row.node_ids.map((id) => (
                      <li key={id}><Link to={`/admin/chapters/${encodeURIComponent(chapter.id)}/nodes/${encodeURIComponent(id)}`}><RichText text={titles.get(id) ?? id} /></Link></li>
                    ))}</ul>
                    : <span className="muted">{row.reason ?? 'причина не указана'}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>
      {rows.length > limit && (
        <Button mt="md" variant="default" onClick={() => setLimit(limit + PAGE)}>Показать ещё, осталось {formatInt(rows.length - limit)}</Button>
      )}
    </>
  );
}

export function CoverageTab({ chapter }: { chapter: ChapterDetail }) {
  const [isUncovered, setUncovered] = useState(false);
  const query = useCoverage(chapter.id, isUncovered);
  return (
    <QueryView query={query}>
      {({ data: rows, meta }) => {
        const total = meta?.total ?? rows.length;
        if (total === 0) return <EmptyState icon={<IconChecklist size={32} aria-hidden />} title="Таблицы покрытия ещё нет" text="Она появится вместе со слоем." />;
        const covered = meta?.covered ?? rows.filter((r) => r.node_ids.length > 0).length;
        return (
          <>
            <div className="coverage-head">
              <p><strong className="coverage-value num">{formatPercent(covered, total)}</strong> единиц главы вошли в шаги: {formatInt(covered)} из {formatInt(total)}. Остальные пропущены с причиной.</p>
              <Meter share={covered / total} />
            </div>
            <div className="toolbar">
              <FilterBar label="Какие единицы показать" value={isUncovered ? 'out' : 'all'} onChange={(v) => setUncovered(v === 'out')} options={[
                { value: 'all', label: 'Все', count: total },
                { value: 'out', label: 'Не вошли', count: meta?.skipped ?? total - covered },
              ]} />
            </div>
            {rows.length === 0 ? <EmptyState title="Непокрытых единиц нет" /> : <Rows key={String(isUncovered)} rows={rows} chapter={chapter} />}
          </>
        );
      }}
    </QueryView>
  );
}
