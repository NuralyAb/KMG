import { useComputedColorScheme, useMantineColorScheme } from '@mantine/core';
import {
  IconBook2, IconBooks, IconChartBar, IconListDetails, IconMenu2, IconMoon, IconSearch, IconShieldCheck, IconSun, IconX,
} from '@tabler/icons-react';
import { Suspense, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { isActive, useHealth, useRuns } from '@/api/queries';
import { Loading } from '@/ui/states';
import { ErrorBoundary } from './ErrorBoundary';
import './shell.css';

const NAV = [
  [
    { to: '/', label: 'Главы', Icon: IconBook2 },
    { to: '/books', label: 'Книги', Icon: IconBooks },
    { to: '/review', label: 'Проверка пакета', Icon: IconShieldCheck },
    { to: '/search', label: 'Поиск', Icon: IconSearch },
  ],
  [
    { to: '/runs', label: 'Запуски', Icon: IconListDetails },
    { to: '/metrics', label: 'Расход', Icon: IconChartBar },
  ],
];

const isCurrent = (to: string, path: string): boolean =>
  (to === '/' ? path === '/' || path.startsWith('/chapters') : path.startsWith(to));

function Health() {
  const { data, isPending, isError } = useHealth();
  if (isPending) return <span className="app-health" data-state="wait">Проверка связи</span>;
  if (isError || !data) return <span className="app-health" data-state="down" role="status">Сервер недоступен</span>;
  const missing = [!data.claude_found && 'нет Claude Code', !data.ffmpeg_found && 'нет ffmpeg'].filter(Boolean).join(', ');
  const text = [data.provider, data.model].filter(Boolean).join(' · ');
  return <span className="app-health" data-state={missing ? 'wait' : 'ok'} title={missing || 'Сервер на связи'}>{missing ? `${text}, ${missing}` : text}</span>;
}

function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme('light', { getInitialValueInEffect: false });
  const isDark = scheme === 'dark';
  return (
    <button type="button" className="app-icon" onClick={() => setColorScheme(isDark ? 'light' : 'dark')}
      aria-label={isDark ? 'Светлая тема' : 'Тёмная тема'}>
      {isDark ? <IconSun size={20} /> : <IconMoon size={20} />}
    </button>
  );
}

function QuickSearch() {
  const navigate = useNavigate();
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const q = String(new FormData(event.currentTarget).get('q') ?? '').trim();
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/search');
  };
  return (
    <form role="search" className="app-find" onSubmit={submit}>
      <IconSearch size={18} aria-hidden />
      <input name="q" type="search" placeholder="Найти утверждение" aria-label="Найти утверждение" autoComplete="off" />
    </form>
  );
}

export function Shell() {
  const [isOpen, setOpen] = useState(false);
  const { pathname } = useLocation();
  const sheet = useRef<HTMLElement>(null);
  const isFirst = useRef(true);
  const active = useRuns().data?.filter(isActive).length ?? 0;

  // новый экран: меню закрыто, фокус на листе, прокрутка вверх
  useEffect(() => {
    setOpen(false);
    if (isFirst.current) {
      isFirst.current = false;
      return;
    }
    window.scrollTo(0, 0);
    sheet.current?.focus({ preventScroll: true });
  }, [pathname]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const close = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [isOpen]);

  return (
    <div className="app">
      <a className="app-skip" href="#main">К содержанию</a>
      <header className="app-top">
        <button type="button" className="app-icon app-burger" aria-expanded={isOpen} aria-controls="nav" aria-label="Меню" onClick={() => setOpen(!isOpen)}>
          {isOpen ? <IconX size={22} /> : <IconMenu2 size={22} />}
        </button>
        <Link to="/" className="app-brand"><img src="/icon.svg" width={28} height={28} alt="" />Глава → курс</Link>
        <QuickSearch />
        <div className="app-top-end"><Health /><ThemeToggle /></div>
      </header>
      <nav id="nav" className="app-nav" aria-label="Разделы" data-open={isOpen || undefined}>
        {NAV.map((group) => (
          <ul key={group[0]?.to}>
            {group.map(({ to, label, Icon }) => (
              <li key={to}>
                <Link to={to} aria-current={isCurrent(to, pathname) ? 'page' : undefined}>
                  <Icon aria-hidden />{label}
                  {to === '/runs' && active > 0 && <span className="app-count" aria-label={`идёт: ${active}`}>{active}</span>}
                </Link>
              </li>
            ))}
          </ul>
        ))}
      </nav>
      <main id="main" className="app-sheet" ref={sheet} tabIndex={-1}>
        <div className="app-page">
          <ErrorBoundary key={pathname}>
            <Suspense fallback={<Loading />}><Outlet /></Suspense>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
