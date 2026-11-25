import { ActionIcon, Button, Menu } from '@mantine/core';
import {
  IconActivity, IconAlertTriangleFilled, IconArrowRight, IconBook, IconCalendarTime, IconChartBar, IconCheck, IconChevronDown, IconChevronRight,
  IconCircleCheckFilled, IconClock, IconCpu, IconDots, IconEye, IconLoader2, IconLock, IconPlayerPlay, IconRefresh, IconSchool, IconShieldCheck, IconSitemap, IconStack2,
} from '@tabler/icons-react';
import { useState, type CSSProperties, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { courseHref } from '@/api/client';
import { useChapters, useDomains, useHealth, useRuns } from '@/api/queries';
import type { ChapterCard } from '@/api/types';
import { counted, formatPercent, FORMS } from '@/lib/format';
import { TableScroll } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { BuildDialog } from '../runs/BuildDialog';
import { ago, coverageOf, eventsOf, pipelineOf, qualityOf, sourceOf, stageOf, totalsOf, updatedAt, type Attention, type PipelineStep } from './facts';
import { useAttention } from './useAttention';
import './overview.css';

const LAST_CHAPTERS = 6;
const LAST_EVENTS = 5;
const TOP_ATTENTION = 4;
const chapterPath = (id: string): string => `/admin/chapters/${encodeURIComponent(id)}`;

/** Волна показывает настоящие значения по главам, от меньшего к большему. */
function Wave({ values, id }: { values: number[]; id: string }) {
  const sorted = [...values].sort((a, b) => a - b);
  const points = sorted.length > 1 ? sorted : [0, ...sorted];
  const max = Math.max(1e-9, ...points);
  const at = (i: number): [number, number] => [(i / (points.length - 1)) * 120, 46 - ((points[i] ?? 0) / max) * 38];
  let line = `M${at(0).join(',')}`;
  for (let i = 1; i < points.length; i += 1) {
    const [x0, y0] = at(i - 1);
    const [x1, y1] = at(i);
    line += `C${(x0 + x1) / 2},${y0} ${(x0 + x1) / 2},${y1} ${x1},${y1}`;
  }
  return (
    <svg className="stat-wave" viewBox="0 0 120 50" preserveAspectRatio="none" aria-hidden>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".28" /><stop offset="1" stopColor="currentColor" stopOpacity=".03" /></linearGradient></defs>
      <path d={`${line}L120,50L0,50Z`} fill={`url(#${id})`} /><path d={line} fill="none" stroke="currentColor" strokeOpacity=".35" strokeWidth="1" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

interface StatProps { icon: ReactNode; title: string; value: ReactNode; note: ReactNode; tone?: 'brand' | 'good' | 'bad'; noteTone?: 'good' | 'bad' | 'muted'; values: number[]; id: string }

function Stat({ icon, title, value, note, tone = 'brand', noteTone = 'muted', values, id }: StatProps) {
  return (
    <div className="stat card" data-tone={tone}>
      <span className="stat-icon" aria-hidden>{icon}</span>
      <div className="stat-text">
        <span className="stat-title">{title}</span>
        <strong className="num">{value}</strong>
        <span className="stat-note num" data-tone={noteTone}>{note}</span>
      </div>
      <Wave values={values} id={id} />
    </div>
  );
}

const STEP_ICON: Record<PipelineStep['state'], ReactNode> = {
  done: <IconCheck size={18} stroke={2.6} aria-hidden />, current: <span className="flow-dot" />, waiting: <IconClock size={16} aria-hidden />,
};
const STEP_WORD: Record<PipelineStep['state'], string> = { done: 'Готово', current: 'В работе', waiting: 'Ожидает' };

function Pipeline({ chapters }: { chapters: ChapterCard[] }) {
  const { data: health } = useHealth();
  const steps = pipelineOf(chapters);
  return (
    <section className="card pipeline" aria-labelledby="pipeline">
      <div className="card-head">
        <h2 id="pipeline"><IconSitemap aria-hidden />Конвейер публикации</h2>
        {health && <span className="card-aside">Модель: <b>{health.model}</b></span>}
      </div>
      <TableScroll label="Этапы конвейера">
        <ol className="flow">
          {steps.map((s, i) => (
            <li key={s.title} data-state={s.state}>
              <span className="flow-mark">{i === steps.length - 1 && s.done === 0 ? <IconLock size={16} aria-hidden /> : STEP_ICON[s.state]}</span>
              <span className="flow-title">{i + 1}. {s.title}</span>
              <span className="flow-note num">{STEP_WORD[s.state]} • {s.done} из {s.total}</span>
              <span className="flow-bar" aria-hidden><i style={{ '--share': s.total ? s.done / s.total : 0 } as CSSProperties} /></span>
            </li>
          ))}
        </ol>
      </TableScroll>
    </section>
  );
}

const QUALITY_ICON = {
  good: <IconCircleCheckFilled aria-hidden />, warn: <IconRefresh aria-hidden />, bad: <IconAlertTriangleFilled aria-hidden />, info: <IconLoader2 aria-hidden />, neutral: <IconClock aria-hidden />,
};

function ChapterRows({ chapters, onBuild }: { chapters: ChapterCard[]; onBuild: (c: ChapterCard) => void }) {
  const now = Date.now();
  const navigate = useNavigate();
  const rows = [...chapters].sort((a, b) => updatedAt(b) - updatedAt(a)).slice(0, LAST_CHAPTERS);
  return (
    <section className="card last" aria-labelledby="last">
      <div className="card-head">
        <h2 id="last"><IconBook aria-hidden />Последние главы</h2>
        <Link className="card-link" to="/admin/chapters">Все главы <IconArrowRight size={17} aria-hidden /></Link>
      </div>
      <TableScroll label="Последние главы">
        <table className="table ov-table">
          <thead><tr><th>Глава</th><th>Источник</th><th>Этап</th><th>Покрытие</th><th>Статус качества</th><th>Обновлено</th><th><span className="visually-hidden">Действия</span></th></tr></thead>
          <tbody>
            {rows.map((c) => {
              const source = sourceOf(c.book);
              const stage = stageOf(c);
              const quality = qualityOf(c);
              const course = courseHref(c.course_url);
              return (
                <tr key={c.id}>
                  <td className="ov-table-title"><Link to={chapterPath(c.id)}>{c.title}</Link></td>
                  <td>{source.who}{source.where && <><br /><span className="muted">({source.where})</span></>}</td>
                  <td><span className="tag" data-tone={stage.tone}>{stage.text}</span></td>
                  <td>{coverageOf(c) === null ? '—' : formatPercent(c.counts.units_covered, c.counts.units)}</td>
                  <td><span className="tag" data-tone={quality.tone}>{QUALITY_ICON[quality.tone]}{quality.text}</span></td>
                  <td className="nowrap">{ago(updatedAt(c), now)}</td>
                  <td>
                    <Menu position="bottom-end" withinPortal>
                      <Menu.Target><ActionIcon variant="subtle" color="gray" aria-label={`Действия: ${c.title}`}><IconDots size={18} /></ActionIcon></Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item leftSection={<IconBook size={16} />} onClick={() => navigate(chapterPath(c.id))}>Открыть главу</Menu.Item>
                        {course && <Menu.Item leftSection={<IconEye size={16} />} onClick={() => navigate(`${chapterPath(c.id)}/preview`)}>Предпросмотр курса</Menu.Item>}
                        <Menu.Item leftSection={<IconPlayerPlay size={16} />} disabled={c.active_run !== null} onClick={() => onBuild(c)}>Собрать</Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </TableScroll>
    </section>
  );
}

function AttentionCard({ items }: { items: Attention[] }) {
  return (
    <section className="card attention" aria-labelledby="attention">
      <div className="card-head">
        <h2 id="attention"><IconAlertTriangleFilled className="icon-bad" aria-hidden />Требуют внимания</h2>
        <span className="badge" data-tone={items.length ? 'bad' : 'good'} aria-label={`всего: ${items.length}`}>{items.length}</span>
      </div>
      {items.length === 0 ? <p className="muted">Замечаний нет.</p> : (
        <ul>
          {items.slice(0, TOP_ATTENTION).map((a) => (
            <li key={a.id}><Link to={a.to}><i className="dot" data-tone={a.level} aria-hidden /><span><span>{a.text}</span><small>{a.where}</small></span><IconChevronRight size={18} aria-hidden /></Link></li>
          ))}
        </ul>
      )}
      <Button component={Link} to="/admin/quality" variant="outline" fullWidth rightSection={<IconArrowRight size={17} aria-hidden />}>Перейти к проверкам</Button>
    </section>
  );
}

function Activity({ chapters }: { chapters: ChapterCard[] }) {
  const runs = useRuns().data ?? [];
  const now = Date.now();
  const events = eventsOf(chapters, runs, LAST_EVENTS);
  return (
    <section className="card activity" aria-labelledby="activity">
      <div className="card-head">
        <h2 id="activity"><IconActivity aria-hidden />Активность</h2>
        <Link className="card-link card-link-small" to="/admin/runs">Все прогоны <IconArrowRight size={14} aria-hidden /></Link>
      </div>
      {events.length === 0 ? <p className="muted">Событий ещё не было.</p> : (
        <ul>
          {events.map((e) => (
            <li key={e.id}><Link to={e.to}>
              <span className="activity-mark" data-kind={e.kind} aria-hidden>{e.kind === 'run' ? <IconRefresh size={18} /> : <IconStack2 size={18} />}</span>
              <span><span>{e.title}</span><small>{e.where}</small></span>
              <span className="activity-time">{ago(e.at, now)}<i className="dot" data-tone={e.state} aria-hidden /></span>
            </Link></li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StatusBar({ chapters }: { chapters: ChapterCard[] }) {
  const health = useHealth();
  const domains = useDomains().data ?? [];
  const last = Math.max(0, ...chapters.map(updatedAt));
  const isOk = Boolean(health.data) && !health.isError && !(health.data?.provider === 'claude_code' && !health.data.claude_found);
  return (
    <footer className="status card">
      <span><IconBook aria-hidden />Глав в реестре: <b>{chapters.length}</b></span>
      <span><IconStack2 aria-hidden />Доменные пакеты: <b>{domains.join(', ') || '—'}</b></span>
      <span><IconCpu aria-hidden />Поставщик: <b>{health.data?.provider ?? '—'}</b></span>
      <span><IconCalendarTime aria-hidden />Последнее обновление: <b>{last ? new Date(last).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}</b></span>
      <span className="tag" data-tone={isOk ? 'good' : 'bad'} role="status"><i className="dot" data-tone={isOk ? 'good' : 'bad'} aria-hidden />{isOk ? 'Система в порядке' : 'Проверьте систему'}</span>
    </footer>
  );
}

function RunButton({ chapters, onBuild }: { chapters: ChapterCard[]; onBuild: (c: ChapterCard) => void }) {
  return (
    <Menu position="bottom-end" withinPortal width={360}>
      <Menu.Target>
        <Button size="md" leftSection={<IconPlayerPlay size={18} aria-hidden />} rightSection={<IconChevronDown size={18} aria-hidden />} disabled={chapters.length === 0}>Запустить прогон</Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>Какую главу собрать. Перед стартом будет вопрос</Menu.Label>
        {chapters.map((c) => <Menu.Item key={c.id} disabled={c.active_run !== null} onClick={() => onBuild(c)}>{c.title}</Menu.Item>)}
      </Menu.Dropdown>
    </Menu>
  );
}

function Overview({ chapters, onBuild }: { chapters: ChapterCard[]; onBuild: (c: ChapterCard) => void }) {
  const items = useAttention();
  const totals = totalsOf(chapters, Date.now());
  const serious = items.filter((i) => i.level === 'bad').length;
  return (
    <>
      <div className="stats">
        <Stat id="w1" icon={<IconBook />} title="Главы в работе" value={totals.started} note={totals.fresh ? `обновлено за неделю: ${totals.fresh}` : `из ${totals.chapters} в реестре`} noteTone={totals.fresh ? 'good' : 'muted'}
          values={chapters.map((c) => c.stages.filter((s) => s.state !== 'missing').length)} />
        <Stat id="w2" icon={<IconSchool />} title="Курсы готовы" value={totals.courses} note={`опубликовано: ${totals.published}`} values={chapters.map((c) => c.counts.nodes)} />
        <Stat id="w3" icon={<IconShieldCheck />} title="Проверка качества" value={items.length} note={serious ? `серьёзных: ${serious}` : 'серьёзных нет'} noteTone={serious ? 'bad' : 'good'}
          values={chapters.map((c) => items.filter((i) => i.where === c.title).length)} />
        <Stat id="w4" tone="good" icon={<IconChartBar />} title="Среднее покрытие" value={totals.coverage === null ? '—' : formatPercent(totals.covered, totals.units)}
          note={totals.units ? `${totals.covered} из ${counted(totals.units, FORMS.unit)}` : 'слоёв ещё нет'} noteTone="good" values={chapters.map((c) => coverageOf(c) ?? 0)} />
      </div>
      <div className="board">
        <div className="board-main"><Pipeline chapters={chapters} /><ChapterRows chapters={chapters} onBuild={onBuild} /></div>
        <div className="board-side"><AttentionCard items={items} /><Activity chapters={chapters} /></div>
      </div>
      <StatusBar chapters={chapters} />
    </>
  );
}

export default function OverviewPage() {
  const query = useChapters();
  const navigate = useNavigate();
  const [target, setTarget] = useState<ChapterCard | null>(null);
  const chapters = query.data ?? [];
  return (
    <>
      <PageHeader title="Панель управления" docTitle="Обзор" subtitle="Конвейер: глава → учебный слой → демо-курс" actions={<RunButton chapters={chapters} onBuild={setTarget} />} />
      <QueryView query={query} rows={5}>
        {(list) => list.length === 0
          ? <EmptyState icon={<IconBook size={32} aria-hidden />} title="Глав пока нет" text="Загрузите книгу и выберите в ней главу." action={<Link to="/admin/books">Открыть конструктор курсов</Link>} />
          : <Overview chapters={list} onBuild={setTarget} />}
      </QueryView>
      {target && (
        <BuildDialog key={target.id} isOpen command="build" target={target} onClose={() => setTarget(null)} onStarted={() => navigate(`${chapterPath(target.id)}?tab=build`)} />
      )}
    </>
  );
}
