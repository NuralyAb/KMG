import { Button, Skeleton } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { ApiError, errorMessage } from '@/api/client';

const ROW_HEIGHT = 56;

export function Loading({ rows = 5, label = 'Загрузка' }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="state-loading">
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} height={ROW_HEIGHT} radius="sm" />)}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isMissing = error instanceof ApiError && error.status === 404;
  return (
    <div role="alert" className="note" data-tone="bad">
      <IconAlertTriangle size={20} aria-hidden />
      <div>
        <strong>{isMissing ? 'Не найдено' : 'Не удалось загрузить'}</strong>
        <p>{errorMessage(error)}</p>
        {onRetry && !isMissing && <Button mt="xs" size="sm" variant="default" onClick={onRetry}>Повторить</Button>}
      </div>
    </div>
  );
}

interface EmptyStateProps { icon?: ReactNode; title: string; text?: ReactNode; action?: ReactNode }

export function EmptyState({ icon, title, text, action }: EmptyStateProps) {
  return (
    <div className="state-empty">
      {icon}
      <strong>{title}</strong>
      {text && <p>{text}</p>}
      {action}
    </div>
  );
}

interface QueryLike<T> { data: T | undefined; isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown }

/** Загрузка, ошибка, данные: один и тот же порядок на каждом экране. Устаревшие данные не прячутся из-за ошибки фона. */
export function QueryView<T>({ query, rows, children }: { query: QueryLike<T>; rows?: number; children: (data: T) => ReactNode }) {
  if (query.data !== undefined) return <>{children(query.data)}</>;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  return <Loading rows={rows} />;
}
