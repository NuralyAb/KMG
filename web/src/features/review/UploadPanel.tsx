import { Button, NativeSelect, Progress } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { IconFileZip, IconUpload } from '@tabler/icons-react';
import { useId, useRef, useState, type DragEvent, type FormEvent } from 'react';
import { errorMessage, uploadForm } from '@/api/client';
import { useChapters, useRefreshAll } from '@/api/queries';
import type { Run } from '@/api/types';
import { packageProblem } from './remarks';

const MB = 1024 * 1024;
const sizeText = (bytes: number): string => `${(bytes / MB).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} МБ`;

/** Загрузка пакета: глава, zip перетаскиванием или кнопкой, ход отправки. Проверка платная, поэтому старт отдельной кнопкой. */
export function UploadPanel({ onStarted }: { onStarted: (run: Run) => void }) {
  const chapters = useChapters().data ?? [];
  const refresh = useRefreshAll();
  const [chapter, setChapter] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [share, setShare] = useState(0);
  const [isOver, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const errorId = useId();
  const selected = chapter || chapters[0]?.id || '';

  const upload = useMutation({
    mutationFn: (zip: File) => {
      const form = new FormData();
      form.append('chapter', selected);
      form.append('file', zip);
      return uploadForm<Run>('/api/reviews', form, setShare);
    },
    onSuccess: (run) => {
      setFile(null);
      onStarted(run);
    },
    onSettled: refresh,
  });

  const pick = (next: File | undefined): void => {
    if (!next) return;
    const found = packageProblem(next);
    upload.reset();
    setProblem(found);
    setFile(found ? null : next);
  };

  const drop = (event: DragEvent): void => {
    event.preventDefault();
    setOver(false);
    pick(event.dataTransfer.files[0]);
  };

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (!file || !selected) return;
    setShare(0);
    upload.mutate(file);
  };

  const error = problem ?? (upload.isError ? errorMessage(upload.error) : null);
  return (
    <form className="upload" onSubmit={submit}>
      <NativeSelect label="Глава, с которой сверять" value={selected} onChange={(e) => setChapter(e.currentTarget.value)} disabled={upload.isPending}
        data={chapters.map((c) => ({ value: c.id, label: c.title }))} />
      <div className="drop" data-over={isOver || undefined} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
        <IconFileZip size={28} aria-hidden />
        <div className="drop-text">
          <strong>{file ? file.name : 'Zip с package.json и папкой frames'}</strong>
          <span className="muted">{file ? sizeText(file.size) : 'Перетащите сюда или выберите на диске, до 80 МБ'}</span>
        </div>
        <Button variant="default" disabled={upload.isPending} onClick={() => input.current?.click()}>{file ? 'Другой файл' : 'Выбрать файл'}</Button>
        <input ref={input} type="file" accept=".zip,application/zip" className="visually-hidden" tabIndex={-1} aria-label="Файл пакета"
          aria-invalid={problem !== null} aria-describedby={error ? errorId : undefined}
          onChange={(e) => { pick(e.currentTarget.files?.[0]); e.currentTarget.value = ''; }} />
      </div>
      {upload.isPending && (
        <div className="upload-progress" role="status">
          <span className="num">{share < 1 ? `Отправлено ${Math.floor(share * 100)} %` : 'Отправлено, сервер разбирает архив'}</span>
          <Progress value={share * 100} size="sm" aria-label="Ход отправки" />
        </div>
      )}
      {error && <p id={errorId} role="alert" className="text-bad">{error}</p>}
      <div className="upload-actions">
        <Button type="submit" disabled={!file || !selected} loading={upload.isPending} leftSection={<IconUpload size={18} aria-hidden />}>Загрузить и проверить</Button>
        <span className="muted">Проверку ведёт модель, она платная.</span>
      </div>
    </form>
  );
}
