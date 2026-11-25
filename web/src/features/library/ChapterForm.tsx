import { Button, NativeSelect, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlus } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '@/api/client';
import { useCreateChapter, useDomains } from '@/api/queries';
import type { SourceDetail } from '@/api/types';
import { parseRanges } from './files';

const DOMAIN: Record<string, string> = { general: 'Общая', geology: 'Геология' };

export function ChapterForm({ source }: { source: SourceDetail }) {
  const create = useCreateChapter(source.id);
  const domains = useDomains().data ?? [];
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [book, setBook] = useState(source.name.replace(/\.[a-z]+$/i, ''));
  const [pages, setPages] = useState('');
  const [domain, setDomain] = useState('');
  const [problem, setProblem] = useState<string | null>(null);

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    const ranges = parseRanges(pages);
    setProblem(ranges ? null : 'Запишите страницы так: 5-20 или 5-20, 25');
    if (!ranges) return;
    create.mutate({ title, book: book.trim() || null, pages: ranges, domain: domain || domains[0] || 'general' }, {
      onSuccess: ({ id }) => {
        notifications.show({ message: 'Глава создана. Осталось собрать её' });
        navigate(`/chapters/${encodeURIComponent(id)}?tab=build`);
      },
    });
  };

  return (
    <form className="lib-form" onSubmit={submit}>
      <TextInput label="Название главы" required maxLength={200} value={title} onChange={(e) => setTitle(e.currentTarget.value)} />
      <TextInput label="Книга" description="Так она будет названа в курсе" maxLength={300} value={book} onChange={(e) => setBook(e.currentTarget.value)} />
      <TextInput label="Страницы" description={`В файле страницы 1–${source.page_list.at(-1)?.page ?? source.pages}`} required placeholder="5-20" inputMode="text" value={pages}
        error={problem} onChange={(e) => setPages(e.currentTarget.value)} />
      <NativeSelect label="Предметная область" description="От неё зависят заблуждения, рисунки и проверки" value={domain || domains[0]} onChange={(e) => setDomain(e.currentTarget.value)}
        data={domains.map((d) => ({ value: d, label: DOMAIN[d] ?? d }))} />
      {create.isError && <p role="alert" className="lib-bad">{errorMessage(create.error)}</p>}
      <div><Button type="submit" loading={create.isPending} leftSection={<IconPlus size={18} aria-hidden />}>Создать главу</Button></div>
    </form>
  );
}
