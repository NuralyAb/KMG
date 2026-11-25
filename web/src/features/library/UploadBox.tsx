import { Button, Checkbox, Progress } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { IconFileUpload } from '@tabler/icons-react';
import { useId, useRef, useState, type DragEvent } from 'react';
import { errorMessage, uploadForm } from '@/api/client';
import { useRefreshAll } from '@/api/queries';
import type { Source } from '@/api/types';
import { counted, FORMS } from '@/lib/format';
import { EXTENSIONS, fileProblem, MAX_FILE_MB } from './files';

/** Файлы отправляются по одному: ошибка одного не мешает остальным. Чтение моделью платное, поэтому по умолчанию выключено. */
export function UploadBox() {
  const refresh = useRefreshAll();
  const [vision, setVision] = useState(false);
  const [isOver, setOver] = useState(false);
  const [share, setShare] = useState(0);
  const [sending, setSending] = useState('');
  const [problems, setProblems] = useState<string[]>([]);
  const [done, setDone] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const errorId = useId();

  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      for (const file of files) {
        const problem = fileProblem(file);
        if (problem) {
          setProblems((old) => [...old, `${file.name}: ${problem}`]);
          continue;
        }
        setSending(file.name);
        setShare(0);
        const form = new FormData();
        form.append('vision', String(vision));
        form.append('file', file);
        try {
          await uploadForm<Source>('/api/library', form, setShare);
          setDone((n) => n + 1);
        } catch (error: unknown) {
          setProblems((old) => [...old, `${file.name}: ${errorMessage(error)}`]);
        }
        refresh();
      }
    },
  });

  const send = (list: FileList | null): void => {
    if (!list?.length || upload.isPending) return;
    setProblems([]);
    setDone(0);
    upload.mutate([...list]);
  };

  const drop = (event: DragEvent): void => {
    event.preventDefault();
    setOver(false);
    send(event.dataTransfer.files);
  };

  return (
    <section className="lib-upload" aria-label="Загрузка файлов">
      <div className="lib-drop" data-over={isOver || undefined} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
        <IconFileUpload size={28} aria-hidden />
        <div className="lib-drop-text">
          <strong>Перетащите книги сюда</strong>
          <span className="muted">PDF, DOCX, MD, TXT, PNG, JPG, до {MAX_FILE_MB} МБ каждый</span>
        </div>
        <Button loading={upload.isPending} onClick={() => input.current?.click()}>Выбрать файлы</Button>
        <input ref={input} type="file" multiple accept={EXTENSIONS.join(',')} className="visually-hidden" tabIndex={-1} aria-label="Файлы книг"
          aria-describedby={problems.length ? errorId : undefined} onChange={(e) => { send(e.currentTarget.files); e.currentTarget.value = ''; }} />
      </div>
      <Checkbox checked={vision} onChange={(e) => setVision(e.currentTarget.checked)} disabled={upload.isPending}
        label="Сразу прочитать моделью сканы и сомнительные страницы" description="Платно. Страницы уйдут выбранной модели. Можно сделать позже" />
      {upload.isPending && (
        <div role="status" className="lib-progress">
          <span className="num">{share < 1 ? `${sending}: отправлено ${Math.floor(share * 100)} %` : `${sending}: сервер сохраняет файл`}</span>
          <Progress value={share * 100} size="sm" aria-label="Ход отправки" />
        </div>
      )}
      {!upload.isPending && done > 0 && <p role="status">Загружено: {counted(done, FORMS.file)}</p>}
      {problems.length > 0 && <ul id={errorId} role="alert" className="lib-problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
    </section>
  );
}
