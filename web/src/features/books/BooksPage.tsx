import { Button, Checkbox, NativeSelect, TextInput } from '@mantine/core';
import { IconBook2, IconUpload } from '@tabler/icons-react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage, get, post, uploadForm } from '@/api/client';
import { useRefreshAll } from '@/api/queries';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { pagesText, parsePages, rangesOf, type Section } from './pages';
import './books.css';

interface Book { id: string; title: string; file: string; uploaded: boolean; has_pdf: boolean }
interface BookDetail extends Book { sections: Section[]; first_page: number | null; last_page: number | null; domains: string[] }

function Upload({ onDone }: { onDone: (id: string) => void }) {
  const [md, setMd] = useState<File | null>(null);
  const [pdf, setPdf] = useState<File | null>(null);
  const [share, setShare] = useState(0);
  const mdInput = useRef<HTMLInputElement>(null);
  const pdfInput = useRef<HTMLInputElement>(null);
  const send = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (md) form.append('file', md);
      if (pdf) form.append('pdf', pdf);
      return uploadForm<Book>('/api/books', form, setShare);
    },
    onSuccess: (book) => { setMd(null); setPdf(null); onDone(book.id); },
  });
  return (
    <section className="section" aria-labelledby="upload">
      <h2 id="upload">Загрузить книгу или главу</h2>
      <p className="muted">Текст в md с метками страниц обязателен. PDF нужен для сверки со сканом. Файлы остаются на этом компьютере.</p>
      <div className="book-upload">
        <Button variant="default" onClick={() => mdInput.current?.click()}>{md ? md.name : 'Текст .md'}</Button>
        <Button variant="default" onClick={() => pdfInput.current?.click()}>{pdf ? pdf.name : 'PDF, если есть'}</Button>
        <Button leftSection={<IconUpload size={18} />} disabled={!md} loading={send.isPending} onClick={() => { setShare(0); send.mutate(); }}>Загрузить</Button>
        <input ref={mdInput} type="file" accept=".md" className="visually-hidden" tabIndex={-1} aria-label="Текст книги" onChange={(e) => setMd(e.currentTarget.files?.[0] ?? null)} />
        <input ref={pdfInput} type="file" accept=".pdf" className="visually-hidden" tabIndex={-1} aria-label="PDF книги" onChange={(e) => setPdf(e.currentTarget.files?.[0] ?? null)} />
      </div>
      {send.isPending && <p role="status" className="num">Отправлено {Math.floor(share * 100)} %</p>}
      {send.isError && <p role="alert" className="text-bad">{errorMessage(send.error)}</p>}
    </section>
  );
}

function Contents({ book }: { book: BookDetail }) {
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [title, setTitle] = useState('');
  const [pages, setPages] = useState('');
  const [domain, setDomain] = useState(book.domains.includes('geology') ? 'geology' : book.domains[0] ?? '');
  const navigate = useNavigate();
  const refresh = useRefreshAll();
  const create = useMutation({
    mutationFn: async () => (await post<{ id: string }>(`/api/books/${encodeURIComponent(book.id)}/chapters`, { title: title.trim(), pages: parsePages(pages), domain })).data,
    onSuccess: ({ id }) => { refresh(); navigate(`/admin/chapters/${encodeURIComponent(id)}?tab=build`); },
  });
  const toggle = (s: Section): void => {
    const next = new Set(chosen);
    if (!next.delete(s.id)) next.add(s.id);
    setChosen(next);
    const picked = book.sections.filter((x) => next.has(x.id));
    setPages(pagesText(rangesOf(picked)));
    setTitle(picked[0]?.title.slice(0, 120) ?? '');
  };
  const ranges = parsePages(pages);
  const count = ranges.reduce((n, [a, b]) => n + Math.max(0, b - a + 1), 0);
  const submit = (event: FormEvent): void => { event.preventDefault(); create.mutate(); };
  return (
    <form onSubmit={submit} className="book-grid">
      <div>
        <h2>Оглавление</h2>
        <p className="muted">Найдено программой по заголовкам. Отметьте, что войдёт в один курс.</p>
        {book.sections.length === 0 && <p>Заголовков не нашлось. Укажите страницы справа.</p>}
        <ul className="plain book-sections">
          {book.sections.map((s) => (
            <li key={s.id} style={{ paddingInlineStart: `${Math.min(3, s.level) * 18}px` }}>
              <Checkbox checked={chosen.has(s.id)} onChange={() => toggle(s)} label={<>{s.title} <span className="muted num">{s.first === s.last ? `стр. ${s.first}` : `стр. ${s.first}–${s.last}`}</span></>} />
            </li>
          ))}
        </ul>
      </div>
      <div className="book-new">
        <h2>Новый курс</h2>
        <TextInput label="Название" required minLength={3} maxLength={200} value={title} onChange={(e) => setTitle(e.currentTarget.value)} />
        <TextInput label="Страницы" description={`Можно поправить. В книге ${book.first_page ?? '?'}–${book.last_page ?? '?'}`} required placeholder="9-14, 20-30" value={pages} onChange={(e) => setPages(e.currentTarget.value)} />
        {book.domains.length > 1 && <NativeSelect label="Доменный пакет" value={domain} data={book.domains} onChange={(e) => setDomain(e.currentTarget.value)} />}
        <p className="muted num">{count > 0 ? `Страниц: ${count}` : 'Страницы не выбраны'}</p>
        {create.isError && <p role="alert" className="text-bad">{errorMessage(create.error)}</p>}
        <Button type="submit" fullWidth loading={create.isPending} disabled={count === 0 || title.trim().length < 3}>Создать курс</Button>
        <p className="muted">Создание бесплатно: глава появится в списке. Платная сборка запускается отдельной кнопкой.</p>
      </div>
    </form>
  );
}

export default function BooksPage() {
  const [current, setCurrent] = useState<string | null>(null);
  const refresh = useRefreshAll();
  const books = useQuery({ queryKey: ['books'], queryFn: async ({ signal }) => (await get<Book[]>('/api/books', signal)).data });
  const id = current ?? books.data?.[0]?.id ?? null;
  const detail = useQuery({ queryKey: ['books', id], enabled: id !== null, queryFn: async ({ signal }) => (await get<BookDetail>(`/api/books/${encodeURIComponent(id ?? '')}`, signal)).data });
  return (
    <>
      <PageHeader title="Книги" docTitle="Книги" subtitle="Загрузите книгу, выберите главы и создайте из них курс." />
      <Upload onDone={(book) => { setCurrent(book); refresh(); void books.refetch(); }} />
      <QueryView query={books} rows={3}>
        {(list) => list.length === 0
          ? <EmptyState icon={<IconBook2 size={32} aria-hidden />} title="Книг пока нет" text="Загрузите файл md, и здесь появится оглавление." />
          : <NativeSelect label="Книга" value={id ?? ''} onChange={(e) => setCurrent(e.currentTarget.value)} data={list.map((b) => ({ value: b.id, label: `${b.title}${b.uploaded ? ' (загружена)' : ''}` }))} />}
      </QueryView>
      {id && <QueryView query={detail} rows={6}>{(book) => <Contents key={book.id} book={book} />}</QueryView>}
    </>
  );
}
