import { Button, Modal } from '@mantine/core';
import { IconAlertTriangle, IconEye, IconFileText, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { apiPath, errorMessage } from '@/api/client';
import { useExtract, usePageText, useRemoveChapter, useRemoveSource, useRuns, useSource, useChapters } from '@/api/queries';
import { PAGE_STATES, type LibraryPage, type PageState, type SourceDetail } from '@/api/types';
import { counted, FORMS } from '@/lib/format';
import { PAGE_STATE } from '@/lib/labels';
import { Chip, FilterBar } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, ErrorState, Loading, QueryView } from '@/ui/states';
import { RunLog } from '../runs/RunLog';
import { ChapterForm } from './ChapterForm';
import { PAGE_TONE, sizeText } from './files';
import { SourceChip } from './LibraryPage';
import './library.css';

const VIEWABLE = new Set(['pdf', 'image']);

function PageView({ source, page, stamp }: { source: SourceDetail; page: LibraryPage; stamp: string }) {
  const text = usePageText(source.id, page.page, stamp);
  const image = apiPath(['library', source.id, 'pages', String(page.page), 'image'], { v: stamp });
  return (
    <section className="lib-view" aria-label={`Страница ${page.page}`}>
      <header className="lib-view-head">
        <h3>Страница {page.page}</h3>
        <Chip tone={PAGE_TONE[page.state]}>{PAGE_STATE[page.state]}</Chip>
        {page.method === 'vision' && <Chip tone="brand" icon={<IconEye aria-hidden />}>прочитала модель</Chip>}
      </header>
      {page.reasons.length > 0 && <ul className="lib-reasons">{page.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
      <div className="lib-sides" data-single={!VIEWABLE.has(source.kind) || undefined}>
        <div className="lib-text" role="region" aria-label="Извлечённый текст" tabIndex={0}>
          {text.isError ? <ErrorState error={text.error} onRetry={() => void text.refetch()} />
            : text.data ? (text.data.text || <span className="muted">Текста на странице нет</span>) : <Loading rows={3} />}
        </div>
        {VIEWABLE.has(source.kind) && (
          <a href={`${apiPath(['library', source.id, 'original'])}${source.kind === 'pdf' ? `#page=${page.page}` : ''}`} target="_blank" rel="noreferrer" aria-label="Открыть исходный файл">
            <img key={image} src={image} alt={`Страница ${page.page} исходного файла`} />
          </a>
        )}
      </div>
    </section>
  );
}

function Pages({ source }: { source: SourceDetail }) {
  const [show, setShow] = useState<PageState | 'all'>('all');
  const [chosen, setChosen] = useState<number | null>(null);
  const pages = source.page_list.filter((p) => show === 'all' || p.state === show);
  const current = pages.find((p) => p.page === chosen) ?? pages[0];
  return (
    <section className="section" aria-labelledby="pages">
      <h2 id="pages">Текст по страницам</h2>
      <p className="muted">Из этого текста берутся дословные цитаты. Сверьте сомнительные страницы: ошибка здесь попадёт в курс.</p>
      <FilterBar<PageState | 'all'> label="Какие страницы показать" value={show} onChange={setShow}
        options={[{ value: 'all', label: 'Все', count: source.page_list.length }, ...PAGE_STATES.filter((s) => source.counts[s] > 0).map((s) => ({ value: s, label: PAGE_STATE[s], count: source.counts[s] }))]} />
      <div className="lib-pages" role="group" aria-label="Страницы">
        {pages.map((p) => (
          <button key={p.page} type="button" data-tone={PAGE_TONE[p.state]} aria-pressed={p.page === current?.page} aria-label={`Страница ${p.page}, ${PAGE_STATE[p.state]}`}
            onClick={() => setChosen(p.page)}>{p.page}</button>
        ))}
      </div>
      {current && <PageView source={source} page={current} stamp={source.run ?? ''} />}
    </section>
  );
}

function SourceLog({ id }: { id: string }) {
  const run = useRuns().data?.find((r) => r.id === id);
  return run ? <RunLog key={run.id} run={run} /> : null;
}

function Reading({ source }: { source: SourceDetail }) {
  const extract = useExtract(source.id);
  const weak = source.counts.scan + source.counts.doubtful;
  const canRead = VIEWABLE.has(source.kind);
  if (source.state === 'extracting') return source.run ? <SourceLog id={source.run} /> : <Loading rows={2} />;
  if (source.state === 'failed' || source.state === 'uploaded') {
    return (
      <div className="note" data-tone="bad">
        <IconAlertTriangle size={20} aria-hidden />
        <div>
          <strong>Текст не извлечён</strong>
          <p>Причина — в журнале запуска. Файл на месте, извлечение можно повторить бесплатно.</p>
          <Button mt="xs" size="sm" variant="default" loading={extract.isPending} onClick={() => extract.mutate(false)}>Извлечь ещё раз</Button>
          {extract.isError && <p role="alert" className="lib-bad">{errorMessage(extract.error)}</p>}
          {source.run && <SourceLog id={source.run} />}
        </div>
      </div>
    );
  }
  if (weak === 0 || !canRead || source.chapters.length > 0) return null;
  return (
    <div className="note" data-tone={source.counts.scan ? 'bad' : 'warn'}>
      <IconAlertTriangle size={20} aria-hidden />
      <div>
        <strong>{[source.counts.scan > 0 && `Без текста: ${source.counts.scan}`, source.counts.doubtful > 0 && `Сверить: ${source.counts.doubtful}`].filter(Boolean).join('. ')}</strong>
        <p>Модель может прочитать эти страницы по изображению. Это платно, страницы уйдут выбранной модели. Прочитанное останется с пометкой «сверить».</p>
        <Button mt="xs" size="sm" loading={extract.isPending} onClick={() => extract.mutate(true)}>Прочитать моделью: {counted(weak, FORMS.page)}</Button>
        {extract.isError && <p role="alert" className="lib-bad">{errorMessage(extract.error)}</p>}
      </div>
    </div>
  );
}

function Chapters({ source }: { source: SourceDetail }) {
  const chapters = useChapters().data ?? [];
  const drop = useRemoveChapter();
  return (
    <section className="section" aria-labelledby="chapters">
      <h2 id="chapters">Главы из этой книги</h2>
      {source.chapters.length > 0 && (
        <ul className="lib-chapters">
          {source.chapters.map((id) => (
            <li key={id}>
              <Link to={`/chapters/${encodeURIComponent(id)}`}>{chapters.find((c) => c.id === id)?.title ?? id}</Link>
              <Button size="sm" variant="default" loading={drop.isPending && drop.variables === id} onClick={() => drop.mutate(id)}
                aria-label={`Убрать главу: ${chapters.find((c) => c.id === id)?.title ?? id}`}>Убрать из списка</Button>
            </li>
          ))}
        </ul>
      )}
      {drop.isError && <p role="alert" className="lib-bad">{errorMessage(drop.error)}</p>}
      {source.state === 'ready' ? <ChapterForm source={source} /> : <p className="muted">Главу можно создать, когда текст будет извлечён.</p>}
    </section>
  );
}

function RemoveButton({ source }: { source: SourceDetail }) {
  const [isOpen, setOpen] = useState(false);
  const drop = useRemoveSource();
  const navigate = useNavigate();
  return (
    <>
      <Button variant="default" leftSection={<IconTrash size={18} aria-hidden />} onClick={() => setOpen(true)}>Удалить</Button>
      <Modal opened={isOpen} onClose={() => { drop.reset(); setOpen(false); }} title="Удалить файл из базы знаний?" closeButtonProps={{ 'aria-label': 'Закрыть' }}>
        <p>«{source.name}» и извлечённый из него текст удалятся с диска. Вернуть их нельзя.</p>
        {drop.isError && <p role="alert" className="lib-bad">{errorMessage(drop.error)}</p>}
        <div className="page-actions" style={{ justifyContent: 'flex-end', marginTop: 16 }}>
          <Button variant="default" onClick={() => setOpen(false)}>Оставить</Button>
          <Button color="red" loading={drop.isPending} onClick={() => drop.mutate(source.id, { onSuccess: () => navigate('/library') })}>Удалить файл</Button>
        </div>
      </Modal>
    </>
  );
}

export default function SourcePage() {
  const { id = '' } = useParams();
  const query = useSource(id);
  const source = query.data;
  return (
    <>
      <PageHeader title={source?.name ?? 'Книга'} docTitle={source?.name ?? 'Книга'} above={<Link to="/library">База знаний</Link>}
        subtitle={source && [sizeText(source.bytes), source.pages > 0 && counted(source.pages, FORMS.page)].filter(Boolean).join(', ')}
        actions={source && <><SourceChip source={source} /><RemoveButton source={source} /></>} />
      <QueryView query={query} rows={4}>
        {(found) => (
          <>
            <Reading source={found} />
            {found.page_list.length > 0 && found.state !== 'extracting' && <Chapters source={found} />}
            {found.page_list.length > 0 && found.state !== 'extracting' && <Pages source={found} />}
            {found.page_list.length === 0 && found.state === 'ready' && <EmptyState icon={<IconFileText size={32} aria-hidden />} title="Страниц нет" />}
          </>
        )}
      </QueryView>
    </>
  );
}
