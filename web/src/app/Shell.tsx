import { Menu, useComputedColorScheme, useMantineColorScheme } from '@mantine/core';
import {
  IconArrowRight, IconBell, IconBook, IconBooks, IconChartBar, IconChevronDown, IconHelpCircle, IconHome, IconLogout, IconMenu2, IconMoon, IconPlayerPlay, IconRefresh, IconSchool,
  IconSearch, IconSettings, IconShieldCheck, IconSitemap, IconStack2, IconSun, IconUser, IconUsers, IconX,
} from '@tabler/icons-react';
import { Suspense, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { isActive, useLogout, useMe, useRuns } from '@/api/queries';
import { useAttention } from '@/features/overview/useAttention';
import { Loading } from '@/ui/states';
import { ErrorBoundary } from './ErrorBoundary';
import './shell.css';
import './admin.css';

const NAV = [
  { to: '/admin', label: 'Обзор', Icon: IconHome },
  { to: '/admin/chapters', label: 'Главы', Icon: IconBook },
  { to: '/admin/books', label: 'Конструктор курсов', Icon: IconSitemap },
  { to: '/admin/library', label: 'База знаний', Icon: IconBooks },
  { to: '/admin/layer', label: 'Учебный слой', Icon: IconStack2 },
  { to: '/admin/quality', label: 'Проверки качества', Icon: IconShieldCheck },
  { to: '/admin/media', label: 'Медиа и видео', Icon: IconPlayerPlay },
  { to: '/admin/runs', label: 'Прогоны', Icon: IconRefresh },
  { to: '/admin/roles', label: 'Команда и роли', Icon: IconUsers },
  { to: '/admin/metrics', label: 'Отчёты', Icon: IconChartBar },
  { to: '/admin/model', label: 'Настройки', Icon: IconSettings },
] as const;

// страницы без своей строки в меню
const INSIDE: Readonly<Record<string, string>> = { '/admin/review': '/admin/quality', '/admin/search': '/admin/layer' };

function currentOf(pathname: string): (typeof NAV)[number] {
  const inside = Object.entries(INSIDE).find(([from]) => pathname.startsWith(from));
  const path = inside ? inside[1] : pathname;
  return NAV.find((n) => n.to !== '/admin' && path.startsWith(n.to)) ?? NAV[0];
}

export function ThemeToggle() {
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
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const focus = (event: KeyboardEvent): void => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener('keydown', focus);
    return () => window.removeEventListener('keydown', focus);
  }, []);
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const q = String(new FormData(event.currentTarget).get('q') ?? '').trim();
    navigate(q ? `/admin/search?q=${encodeURIComponent(q)}` : '/admin/search');
  };
  return (
    <form role="search" className="adm-find" onSubmit={submit}>
      <IconSearch size={20} aria-hidden />
      <input ref={input} name="q" type="search" placeholder="Поиск по утверждениям глав…" aria-label="Найти утверждение" autoComplete="off" />
      <kbd aria-hidden>Ctrl K</kbd>
    </form>
  );
}

function Bell() {
  const count = useAttention().length;
  return (
    <Link to="/admin/quality" className="app-icon adm-bell" aria-label={count ? `Требуют внимания: ${count}` : 'Замечаний нет'}>
      <IconBell size={21} />{count > 0 && <i aria-hidden />}
    </Link>
  );
}

function Account() {
  const { data } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  return (
    <Menu position="bottom-end" withinPortal width={220}>
      <Menu.Target>
        <button type="button" className="adm-account">
          <span className="adm-avatar" aria-hidden><IconUser size={20} /></span>
          <span className="adm-account-text"><b>Автор курса</b><small>Администратор</small></span>
          <IconChevronDown size={16} aria-hidden />
        </button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{data?.protected ? 'Вход по паролю' : 'Пароль автора не задан'}</Menu.Label>
        <Menu.Item component={Link} to="/" leftSection={<IconSchool size={17} />}>Экран ученика</Menu.Item>
        {data?.protected && (
          <Menu.Item leftSection={<IconLogout size={17} />} disabled={logout.isPending} onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/') })}>Выйти</Menu.Item>
        )}
      </Menu.Dropdown>
    </Menu>
  );
}

export function Shell() {
  const [isOpen, setOpen] = useState(false);
  const { pathname } = useLocation();
  const sheet = useRef<HTMLElement>(null);
  const isFirst = useRef(true);
  const active = useRuns().data?.filter(isActive).length ?? 0;
  const current = currentOf(pathname);

  // оформление автора действует и на окна, которые рисуются вне этой разметки
  useEffect(() => {
    document.documentElement.dataset.area = 'admin';
    return () => { delete document.documentElement.dataset.area; };
  }, []);

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
    <div className="adm">
      <a className="app-skip" href="#main">К содержанию</a>
      <div className="adm-frame">
        <aside className="adm-side">
          <div className="adm-side-top">
            <Link to="/admin" className="adm-brand"><IconSchool size={34} stroke={1.9} aria-hidden />EDEARN</Link>
            <button type="button" className="app-icon adm-burger" aria-expanded={isOpen} aria-controls="nav" aria-label="Меню" onClick={() => setOpen(!isOpen)}>
              {isOpen ? <IconX size={22} /> : <IconMenu2 size={22} />}
            </button>
          </div>
          <nav id="nav" className="adm-nav" aria-label="Разделы" data-open={isOpen || undefined}>
            <ul>
              {NAV.map(({ to, label, Icon }) => (
                <li key={to}>
                  <Link to={to} aria-current={current.to === to && !pathname.startsWith('/admin/help') ? 'page' : undefined}>
                    <Icon aria-hidden /><span>{label}</span>
                    {to === '/admin/runs' && active > 0 && <span className="adm-count" aria-label={`идёт: ${active}`}>{active}</span>}
                  </Link>
                </li>
              ))}
            </ul>
            <Link to="/admin/help" className="adm-help"><IconHelpCircle aria-hidden /><span><b>Нужна помощь?</b><small>Как собрать курс по шагам</small></span><IconArrowRight size={18} aria-hidden /></Link>
          </nav>
        </aside>
        <div className="adm-body">
          <header className="adm-top">
            <nav className="adm-crumbs" aria-label="Где вы">
              {pathname.replace(/\/$/, '') === '/admin' ? <span>Админ</span> : <Link to="/admin">Админ</Link>}<span aria-hidden>/</span><b>{pathname.startsWith('/admin/help') ? 'Помощь' : current.label}</b>
            </nav>
            <QuickSearch />
            <div className="adm-top-end"><Bell /><ThemeToggle /><i className="adm-rule" aria-hidden /><Account /></div>
          </header>
          <main id="main" className="adm-main" ref={sheet} tabIndex={-1}>
            <ErrorBoundary key={pathname}>
              <Suspense fallback={<Loading />}><Outlet /></Suspense>
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </div>
  );
}
