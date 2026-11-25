import { Button, Checkbox, Modal, Stack } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertTriangle, IconCheck } from '@tabler/icons-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '@/api/client';
import { usePublication, usePublish, useUnpublish } from '@/api/queries';
import type { ChapterDetail, Publication } from '@/api/types';
import { formatDateTime } from '@/lib/format';
import { QueryView } from '@/ui/states';

function Status({ state }: { state: Publication }) {
  if (!state.published_at) return <p className="muted">Ученики этот курс пока не видят.</p>;
  return (
    <div className="note" data-tone={state.is_current ? 'good' : 'warn'}>
      {state.is_current ? <IconCheck size={20} aria-hidden /> : <IconAlertTriangle size={20} aria-hidden />}
      <div>
        <p>{state.is_current ? 'Ученики видят эту версию.' : 'Курс с тех пор пересобран: ученики видят прежнюю версию.'} Опубликовано {formatDateTime(state.published_at)}.</p>
        {state.accepted.length > 0 && <p className="muted">Принято при публикации: {state.accepted.join('; ')}.</p>}
      </div>
    </div>
  );
}

function Body({ chapter, state, onClose }: { chapter: ChapterDetail; state: Publication; onClose: () => void }) {
  const publish = usePublish(chapter.id);
  const unpublish = useUnpublish(chapter.id);
  const [accepted, setAccepted] = useState<ReadonlySet<string>>(new Set());
  const isReady = !state.problem && state.checks.every((c) => accepted.has(c.code));
  const toggle = (code: string, isOn: boolean): void => setAccepted((old) => new Set(isOn ? [...old, code] : [...old].filter((c) => c !== code)));
  const error = publish.error ?? unpublish.error;
  return (
    <Stack gap="md">
      <Status state={state} />
      {state.problem && <div className="note" data-tone="bad" role="alert"><IconAlertTriangle size={20} aria-hidden /><div>{state.problem}</div></div>}
      {state.checks.length > 0 && (
        <fieldset className="publish-checks">
          <legend>Отметьте просмотренное</legend>
          {state.checks.map((c) => <Checkbox key={c.code} label={c.text} checked={accepted.has(c.code)} onChange={(e) => toggle(c.code, e.currentTarget.checked)} />)}
          <Link to={`/admin/chapters/${encodeURIComponent(chapter.id)}?tab=trust`} onClick={onClose}>Посмотреть замечания</Link>
        </fieldset>
      )}
      {error && <p role="alert" className="publish-bad">{errorMessage(error)}</p>}
      <div className="page-actions" style={{ justifyContent: 'flex-end' }}>
        {state.published_at && (
          <Button variant="default" loading={unpublish.isPending} onClick={() => unpublish.mutate(undefined, { onSuccess: () => notifications.show({ message: 'Курс снят с публикации' }) })}>Снять с публикации</Button>
        )}
        <Button disabled={!isReady} loading={publish.isPending}
          onClick={() => publish.mutate([...accepted], { onSuccess: () => { notifications.show({ message: 'Курс опубликован' }); onClose(); } })}>
          {state.published_at ? 'Опубликовать эту версию' : 'Опубликовать'}
        </Button>
      </div>
    </Stack>
  );
}

export function PublishDialog({ chapter, isOpen, onClose }: { chapter: ChapterDetail; isOpen: boolean; onClose: () => void }) {
  const query = usePublication(chapter.id, isOpen);
  // новые замечания требуют новых отметок
  const key = query.data?.checks.map((c) => c.code).join() ?? '';
  return (
    <Modal opened={isOpen} onClose={onClose} title="Публикация курса" closeButtonProps={{ 'aria-label': 'Закрыть' }}>
      <QueryView query={query} rows={2}>{(state) => <Body key={key} chapter={chapter} state={state} onClose={onClose} />}</QueryView>
    </Modal>
  );
}
