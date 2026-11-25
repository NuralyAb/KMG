import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useMe } from '@/api/queries';
import { QueryView } from '@/ui/states';

/** Показывает экран автора только автору. Это удобство: данные закрывает сервер. */
export function AdminGate({ children }: { children: ReactNode }) {
  const query = useMe();
  const { pathname, search } = useLocation();
  return (
    <QueryView query={query} rows={4}>
      {(me) => (me.role === 'admin' ? children : <Navigate to={`/login?to=${encodeURIComponent(pathname + search)}`} replace />)}
    </QueryView>
  );
}
