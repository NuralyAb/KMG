import { NativeSelect, Pagination, TextInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { SEARCH_LIMIT, SEARCH_MIN, useChapters, useSearch } from '@/api/queries';
import type { SearchHit } from '@/api/types';
import { counted, FORMS } from '@/lib/format';
import { PageHeader } from '@/ui/PageHeader';
import { RichText } from '@/ui/RichText';
import { EmptyState, QueryView } from '@/ui/states';
import './search.css';

const DEBOUNCE_MS = 300;

function Hit({ hit, query, chapterTitle }: { hit: SearchHit; query: string; chapterTitle: string }) {
  const anchor = hit.claim_id.split('#').pop() ?? '';
  return (
    <li className="hit">
      <p className="hit-where muted">
        <Link to={`/admin/chapters/${encodeURIComponent(hit.chapter)}/nodes/${encodeURIComponent(hit.node_id)}#${encodeURIComponent(anchor)}`}><RichText text={hit.node_title} /></Link>
        <span>{chapterTitle}</span>{hit.page_pdf !== null && <span className="nowrap">стр. {hit.page_pdf}</span>}
      </p>
      <p className="hit-text"><RichText text={hit.text} query={query} /></p>
      <blockquote className="muted"><RichText text={hit.quote} query={query} /></blockquote>
    </li>
  );
}

function Results({ q, chapter, page, onPage }: { q: string; chapter: string; page: number; onPage: (page: number) => void }) {
  const query = useSearch(q, chapter, page);
  const chapters = useChapters().data ?? [];
  return (
    <QueryView query={query} rows={4}>
      {({ data: hits, meta }) => {
        if (hits.length === 0) return <EmptyState icon={<IconSearch size={32} aria-hidden />} title="Ничего не нашлось" text={`По запросу «${q}» нет утверждений. Попробуйте одно слово или корень слова.`} />;
        const total = meta?.total ?? hits.length;
        const pages = Math.ceil(total / (meta?.limit || SEARCH_LIMIT));
        return (
          <>
            <p className="muted" role="status">{counted(total, FORMS.result)}</p>
            <ol className="hits" aria-busy={query.isPlaceholderData}>
              {hits.map((hit) => <Hit key={`${hit.chapter}-${hit.claim_id}`} hit={hit} query={q} chapterTitle={chapters.find((c) => c.id === hit.chapter)?.title ?? hit.chapter} />)}
            </ol>
            {pages > 1 && <Pagination total={pages} value={page} onChange={onPage} mt="lg" siblings={1} boundaries={1}
              getControlProps={(control) => ({ 'aria-label': control === 'previous' ? 'Предыдущая страница' : control === 'next' ? 'Следующая страница' : control })} />}
          </>
        );
      }}
    </QueryView>
  );
}

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const chapter = params.get('chapter') ?? '';
  const page = Math.max(1, Number.parseInt(params.get('page') ?? '1', 10) || 1);
  const [text, setText] = useState(q);
  const [debounced] = useDebouncedValue(text, DEBOUNCE_MS);
  const chapters = useChapters().data ?? [];

  const update = (next: { q?: string; chapter?: string; page?: number }): void => {
    const merged = { q, chapter, page: 1, ...next };
    const entries = Object.entries(merged).filter(([key, value]) => value !== '' && !(key === 'page' && value === 1));
    setParams(new URLSearchParams(entries.map(([key, value]) => [key, String(value)])), { replace: true });
  };

  // поиск из шапки меняет адрес: поле следует за ним
  useEffect(() => setText(q), [q]);
  useEffect(() => {
    if (debounced.trim() !== q && debounced === text) update({ q: debounced.trim() });
    // адрес меняется только вслед за набранным текстом
  }, [debounced]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <PageHeader title="Поиск" docTitle={q ? `Поиск: ${q}` : 'Поиск'} subtitle="По утверждениям и цитатам всех глав. Регистр и «ё» не важны." />
      <div className="search-bar">
        <TextInput type="search" size="md" aria-label="Что найти" placeholder="Слово или часть фразы" leftSection={<IconSearch size={18} aria-hidden />} autoFocus
          value={text} onChange={(e) => setText(e.currentTarget.value)} />
        <NativeSelect size="md" aria-label="Глава" value={chapter} onChange={(e) => update({ chapter: e.currentTarget.value })}
          data={[{ value: '', label: 'Все главы' }, ...chapters.map((c) => ({ value: c.id, label: c.title }))]} />
      </div>
      {q.trim().length < SEARCH_MIN
        ? <EmptyState title="Введите хотя бы два знака" />
        : <Results q={q.trim()} chapter={chapter} page={page} onPage={(next) => update({ page: next })} />}
    </>
  );
}
