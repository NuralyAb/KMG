import { IconAlertTriangle, IconBooks, IconCheck, IconChevronRight, IconLoader2 } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useSources } from '@/api/queries';
import type { Source } from '@/api/types';
import { counted, formatDateTime, FORMS } from '@/lib/format';
import { SOURCE_STATE } from '@/lib/labels';
import { Chip } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { sizeText } from './files';
import { UploadBox } from './UploadBox';
import './library.css';

export function SourceChip({ source }: { source: Source }) {
  if (source.state === 'failed') return <Chip tone="bad" icon={<IconAlertTriangle aria-hidden />}>{SOURCE_STATE.failed}</Chip>;
  if (source.state !== 'ready') return <Chip tone="brand" icon={<IconLoader2 aria-hidden />}>{SOURCE_STATE[source.state]}</Chip>;
  if (source.counts.scan > 0) return <Chip tone="bad" icon={<IconAlertTriangle aria-hidden />}>без текста: {source.counts.scan}</Chip>;
  if (source.counts.doubtful > 0) return <Chip tone="warn" icon={<IconAlertTriangle aria-hidden />}>сверить: {source.counts.doubtful}</Chip>;
  return <Chip tone="good" icon={<IconCheck aria-hidden />}>{SOURCE_STATE.ready}</Chip>;
}

function SourceRow({ source }: { source: Source }) {
  return (
    <li>
      <Link to={`/library/${encodeURIComponent(source.id)}`}>
        <span className="lib-row-main">
          <strong>{source.name}</strong>
          <span className="muted">
            {[sizeText(source.bytes), source.pages > 0 && counted(source.pages, FORMS.page), source.chapters.length > 0 && counted(source.chapters.length, FORMS.chapter),
              formatDateTime(source.added_at)].filter(Boolean).join(', ')}
          </span>
        </span>
        <SourceChip source={source} />
        <IconChevronRight size={20} aria-hidden />
      </Link>
    </li>
  );
}

export default function LibraryPage() {
  const query = useSources();
  return (
    <>
      <PageHeader title="База знаний" docTitle="База знаний"
        subtitle="Загрузите книгу, проверьте извлечённый текст и выберите страницы: из них соберётся курс. Файлы остаются на этом компьютере, пока вы не запустите модель." />
      <UploadBox />
      <section className="section" aria-labelledby="books">
        <h2 id="books">Загруженные файлы</h2>
        <QueryView query={query} rows={3}>
          {(sources) => (sources.length === 0
            ? <EmptyState icon={<IconBooks size={32} aria-hidden />} title="Здесь пока пусто" text="Первая загруженная книга появится в этом списке." />
            : <ul className="lib-list">{sources.map((s) => <SourceRow key={s.id} source={s} />)}</ul>)}
        </QueryView>
      </section>
    </>
  );
}
