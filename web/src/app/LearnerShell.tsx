import '@fontsource-variable/onest';
import { IconBook2, IconLayoutDashboard, IconLogin2 } from '@tabler/icons-react';
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
  return data.role === 'admin'
    ? <Link to="/admin" className="learn-link"><IconLayoutDashboard size={24} stroke={1.7} aria-hidden />Экран автора</Link>
    : <Link to="/login" className="learn-link"><IconLogin2 size={24} stroke={1.7} aria-hidden />Вход для авторов</Link>;
}

/** Тот же знак, что в самом курсе (course/assets/icons.js). */
function Logo() {
  return (
    <svg viewBox="0 0 48 32" width={42} height={28} fill="currentColor" aria-hidden>
      <path d="M24 1 1 11l23 10 23-10z" /><path d="M10 18v6c0 3 6.3 6 14 6s14-3 14-6v-6l-14 6z" opacity=".72" /><path d="M42.5 13.5H45V24h-2.5z" />
    </svg>
  );
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
      <header className="learn-side">
        <Link to="/" className="learn-logo" aria-label="Глава, все курсы"><Logo />ГЛАВА</Link>
        <nav aria-label="Разделы"><Link to="/" className="learn-link" aria-current={pathname === '/' ? 'page' : undefined}><IconBook2 size={24} stroke={1.7} aria-hidden />Мои курсы</Link></nav>
        <div className="learn-foot"><AuthorLink /></div>
      </header>
      <div className="learn-top"><ThemeToggle /></div>
      <main id="main" className="learn-main" ref={main} tabIndex={-1}><div>{page}</div></main>
    </div>
  );
}
