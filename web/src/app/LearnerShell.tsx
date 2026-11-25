import { Suspense, useEffect, useRef } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useMe } from '@/api/queries';
import { Loading } from '@/ui/states';
import { ErrorBoundary } from './ErrorBoundary';
import { ThemeToggle } from './Shell';
import './shell.css';

function AuthorLink() {
  const { data } = useMe();
  if (!data) return null;
  return data.role === 'admin' ? <Link to="/admin" className="app-switch">Экран автора</Link> : <Link to="/login" className="app-switch">Вход для авторов</Link>;
}

/** Экран ученика: каталог и курс. Данные автора сюда не запрашиваются. */
export function LearnerShell() {
  const { pathname } = useLocation();
  const main = useRef<HTMLElement>(null);
  const isFirst = useRef(true);
  const isCourse = pathname.startsWith('/courses/');

  useEffect(() => {
    if (isFirst.current) {
      isFirst.current = false;
      return;
    }
    window.scrollTo(0, 0);
    main.current?.focus({ preventScroll: true });
  }, [pathname]);

  const page = (
    <ErrorBoundary key={pathname}>
      <Suspense fallback={<Loading />}><Outlet /></Suspense>
    </ErrorBoundary>
  );
  // у курса своя шапка на весь экран
  if (isCourse) return page;
  return (
    <div className="learn">
      <a className="app-skip" href="#main">К содержанию</a>
      <header className="learn-top">
        <Link to="/" className="app-brand"><img src="/icon.svg" width={28} height={28} alt="" />Курсы</Link>
        <div className="app-top-end"><AuthorLink /><ThemeToggle /></div>
      </header>
      <main id="main" className="learn-main" ref={main} tabIndex={-1}><div>{page}</div></main>
    </div>
  );
}
