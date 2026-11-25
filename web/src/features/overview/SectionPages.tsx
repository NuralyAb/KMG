/** Разделы админки, собранные из данных глав: качество, слой, медиа, роли, помощь. */
import { Button } from '@mantine/core';
import { IconChevronRight, IconExternalLink, IconLock, IconLockOpen, IconSchool, IconShieldCheck, IconUser } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useChapters, useCourses, useMe, useReviews } from '@/api/queries';
import { counted, formatInt, formatPercent, FORMS } from '@/lib/format';
import { Meter, TableScroll } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { isStarted, qualityOf } from './facts';
import { useAttention } from './useAttention';
import './overview.css';

const path = (id: string, tab = ''): string => `/admin/chapters/${encodeURIComponent(id)}${tab && `?tab=${tab}`}`;

export function QualityPage() {
  const items = useAttention();
  const reviews = useReviews();
  return (
    <>
      <PageHeader title="Проверки качества" docTitle="Проверки качества" subtitle="Что исправить до публикации. Строка ведёт туда, где это делается."
        actions={<Button component={Link} to="/admin/review" variant="outline" leftSection={<IconShieldCheck size={18} aria-hidden />}>Проверить чужой пакет</Button>} />
      {items.length === 0 ? <EmptyState icon={<IconShieldCheck size={32} aria-hidden />} title="Замечаний нет" /> : (
        <ul className="rows card" aria-label="Замечания">
          {items.map((a) => <li key={a.id}><Link to={a.to}><i className="dot" data-tone={a.level} aria-hidden /><span>{a.text}<small>{a.where}</small></span><IconChevronRight size={18} aria-hidden /></Link></li>)}
        </ul>
      )}
      {Boolean(reviews.data?.length) && (
        <section className="section" aria-labelledby="packages">
          <h2 id="packages">Проверенные пакеты</h2>
          <div className="cards">
            {reviews.data?.map((r) => (
              <article key={r.package_id} className="card">
                <h3><Link to={`/admin/review/${encodeURIComponent(r.package_id)}`}>{r.package_id}</Link></h3>
                <p className="muted">{counted(r.remarks.length, FORMS.remark)}</p>
                <div className="chips"><span className="tag" data-tone="bad">критических {r.counts.critical}</span><span className="tag" data-tone="warn">существенных {r.counts.significant}</span><span className="tag">мелких {r.counts.minor}</span></div>
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

export function LayerPage() {
  const query = useChapters();
  return (
    <>
      <PageHeader title="Учебный слой" docTitle="Учебный слой" subtitle="Единственный источник правды: из слоя собираются курс, задания и ролики."
        actions={<Button component={Link} to="/admin/search" variant="outline">Найти утверждение</Button>} />
      <QueryView query={query}>
        {(chapters) => {
          const built = chapters.filter((c) => c.counts.nodes > 0);
          return built.length === 0 ? <EmptyState title="Слоёв ещё нет" text="Соберите главу, и здесь появится её слой." /> : (
            <div className="card" style={{ padding: 18 }}>
              <TableScroll label="Слои глав">
                <table className="table ov-table">
                  <thead><tr><th>Глава</th><th>Узлы</th><th>Утверждения</th><th>Покрытие</th><th>Статус</th></tr></thead>
                  <tbody>
                    {built.map((c) => {
                      const q = qualityOf(c);
                      return (
                        <tr key={c.id}>
                          <td className="ov-table-title"><Link to={path(c.id)}>{c.title}</Link></td><td>{formatInt(c.counts.nodes)}</td><td>{formatInt(c.counts.claims)}</td>
                          <td>{formatPercent(c.counts.units_covered, c.counts.units)}<Meter share={c.counts.units ? c.counts.units_covered / c.counts.units : 0} /></td>
                          <td><span className="tag" data-tone={q.tone}>{q.text}</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TableScroll>
            </div>
          );
        }}
      </QueryView>
    </>
  );
}

export function MediaPage() {
  const query = useChapters();
  return (
    <>
      <PageHeader title="Медиа и видео" docTitle="Медиа и видео" subtitle="Рисунки и ролики по главам." />
      <QueryView query={query}>
        {(chapters) => {
          const built = chapters.filter((c) => isStarted(c) && c.counts.nodes > 0);
          return built.length === 0 ? <EmptyState title="Медиа ещё нет" text="Рисунки появятся после сборки главы." /> : (
            <div className="cards">
              {built.map((c) => (
                <article key={c.id} className="card">
                  <h2><Link to={path(c.id)}>{c.title}</Link></h2>
                  <div className="chips"><span className="tag" data-tone="brand">{counted(c.counts.illustrations, FORMS.picture)}</span><span className="tag" data-tone={c.counts.videos ? 'good' : 'neutral'}>{counted(c.counts.videos, FORMS.video)}</span></div>
                  <div className="page-actions"><Button component={Link} to={path(c.id, 'pictures')} variant="light" size="sm">Рисунки</Button><Button component={Link} to={path(c.id, 'videos')} variant="light" size="sm">Ролики</Button></div>
                </article>
              ))}
            </div>
          );
        }}
      </QueryView>
    </>
  );
}

export function RolesPage() {
  const me = useMe();
  const courses = useCourses().data?.length ?? 0;
  const isProtected = me.data?.protected ?? false;
  return (
    <>
      <PageHeader title="Команда и роли" docTitle="Команда и роли" subtitle="В приложении две роли. Учётных записей нет: курс открывается без входа, так требует задание." />
      <div className="cards">
        <article className="card">
          <h2><IconUser size={20} aria-hidden style={{ verticalAlign: -4 }} /> Автор</h2>
          <p className="muted">Загружает книги, собирает и публикует курсы, проверяет качество.</p>
          <span className="tag" data-tone={isProtected ? 'good' : 'warn'}>{isProtected ? <IconLock aria-hidden /> : <IconLockOpen aria-hidden />}{isProtected ? 'Вход по паролю' : 'Пароль не задан'}</span>
          {!isProtected && <p className="muted">Чтобы закрыть экран автора, запустите сервер с переменной <code>GLAVA_ADMIN_PASSWORD</code> (от 8 знаков).</p>}
        </article>
        <article className="card">
          <h2><IconSchool size={20} aria-hidden style={{ verticalAlign: -4 }} /> Ученик</h2>
          <p className="muted">Проходит опубликованные курсы. Прогресс хранится в его браузере и автору не виден.</p>
          <span className="tag" data-tone={courses ? 'good' : 'neutral'}>Опубликовано курсов: {courses}</span>
          <div><Button component={Link} to="/" variant="light" size="sm" rightSection={<IconExternalLink size={16} aria-hidden />}>Экран ученика</Button></div>
        </article>
      </div>
    </>
  );
}

const HELP: readonly { title: string; text: string; to: string; link: string }[] = [
  { title: 'Добавьте главу', text: 'Загрузите книгу, отметьте разделы и нажмите «Создать курс». Это бесплатно.', to: '/admin/books', link: 'Конструктор курсов' },
  { title: 'Соберите главу', text: 'Кнопка «Запустить прогон» пройдёт все этапы. Этапы с моделью платные, перед стартом будет вопрос.', to: '/admin/chapters', link: 'Главы' },
  { title: 'Следите за ходом', text: 'Журнал сборки виден сразу. Остановить можно в любой момент: готовые ответы модели не пропадут.', to: '/admin/runs', link: 'Прогоны' },
  { title: 'Исправьте замечания', text: 'Список ведёт прямо к месту, где исправляют.', to: '/admin/quality', link: 'Проверки качества' },
  { title: 'Опубликуйте курс', text: 'На странице главы нажмите «Опубликовать»: курс появится на экране ученика.', to: '/admin/chapters', link: 'Главы' },
];

export function HelpPage() {
  return (
    <>
      <PageHeader title="Как собрать курс" docTitle="Помощь" subtitle="Пять шагов от книги до опубликованного курса." />
      <ol className="help-steps">{HELP.map((h) => <li key={h.title} className="card"><div><h2>{h.title}</h2><p className="muted">{h.text}</p><Link to={h.to}>{h.link}</Link></div></li>)}</ol>
    </>
  );
}
