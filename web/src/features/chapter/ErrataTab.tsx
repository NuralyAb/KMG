import { IconTextSpellcheck } from '@tabler/icons-react';
import { useState } from 'react';
import { useErrata } from '@/api/queries';
import type { ErrataRow } from '@/api/types';
import { ERRATA_KIND, label } from '@/lib/labels';
import { FilterBar, TableScroll } from '@/ui/bits';
import { RichText } from '@/ui/RichText';
import { EmptyState, QueryView } from '@/ui/states';

type Show = 'all' | 'suspect' | 'recognition';

function Table({ rows }: { rows: ErrataRow[] }) {
  return (
    <TableScroll label="Лист опечаток">
      <table className="table table-wide">
        <thead><tr><th className="right">Стр.</th><th>В распознанном тексте</th><th>На скане</th><th>Пояснение</th></tr></thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={`${row.page}-${i}`}>
              <td className="right">{row.page}</td>
              <td className="cell-text"><RichText text={row.md} /></td>
              <td className="cell-text"><RichText text={row.scan} /></td>
              <td className="cell-text">
                <span className={row.kind === 'suspect' ? 'text-warn' : 'muted'}>{label(ERRATA_KIND, row.kind)}</span>
                {row.note && <div><RichText text={row.note} /></div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

export function ErrataTab({ id }: { id: string }) {
  const [show, setShow] = useState<Show>('all');
  const query = useErrata(id);
  return (
    <QueryView query={query}>
      {({ data: rows, meta }) => {
        if (rows.length === 0) return <EmptyState icon={<IconTextSpellcheck size={32} aria-hidden />} title="Опечаток нет" text="Либо сверка со сканом ещё не запускалась, либо расхождений не нашлось." />;
        const count = (kind: string): number => rows.filter((r) => r.kind === kind).length;
        return (
          <>
            <div className="toolbar">
              <FilterBar label="Какие записи показать" value={show} onChange={setShow} options={[
                { value: 'all', label: 'Все', count: rows.length },
                { value: 'suspect', label: 'Сомнительные места издания', count: meta?.suspect ?? count('suspect') },
                { value: 'recognition', label: 'Ошибки распознавания', count: meta?.recognition ?? count('recognition') },
              ]} />
            </div>
            <Table rows={show === 'all' ? rows : rows.filter((r) => r.kind === show)} />
          </>
        );
      }}
    </QueryView>
  );
}
