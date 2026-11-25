import { Button } from '@mantine/core';
import { IconSchool } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useCourses, useMe } from '@/api/queries';
import type { LearnCourse } from '@/api/types';
import { counted, formatPercent, FORMS } from '@/lib/format';
import { Meter } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { useProgress } from './useProgress';
import './learn.css';

export function minutesText(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return [hours > 0 && `${hours} ч`, (rest > 0 || hours === 0) && `${rest} мин`].filter(Boolean).join(' ');
}

function CourseCard({ course }: { course: LearnCourse }) {
  const { done } = useProgress(course);
  const path = `/courses/${encodeURIComponent(course.id)}`;
  const action = done === 0 ? 'Начать' : done >= course.steps ? 'Повторить' : 'Продолжить';
  return (
    <article className="learn-card" aria-labelledby={`c-${course.id}`}>
      <div className="learn-card-main">
        <h2 id={`c-${course.id}`}><Link to={path}>{course.title}</Link></h2>
        {course.book && <p className="muted">{course.book}</p>}
        <p className="learn-card-facts">{counted(course.steps, FORMS.node)}, {counted(course.tasks, FORMS.task)}, {minutesText(course.minutes)}</p>
      </div>
      <div className="learn-card-side">
        <div className="learn-progress">
          <span className="num">{done === 0 ? 'Ещё не начат' : `Пройдено ${done} из ${course.steps}, ${formatPercent(done, course.steps)}`}</span>
          <Meter share={course.steps > 0 ? done / course.steps : 0} />
        </div>
        <Button component={Link} to={path} aria-label={`${action}: ${course.title}`}>{action}</Button>
      </div>
    </article>
  );
}

export default function CatalogPage() {
  const query = useCourses();
  const me = useMe().data;
  return (
    <>
      <PageHeader title="Курсы" docTitle="Курсы" subtitle="Прогресс сохраняется в этом браузере." />
      <QueryView query={query} rows={3}>
        {(courses) => (courses.length === 0
          ? <EmptyState icon={<IconSchool size={32} aria-hidden />} title="Курсов пока нет"
            text={me?.role === 'admin' ? 'Откройте главу на экране автора и опубликуйте курс.' : 'Они появятся, когда автор их опубликует.'}
            action={me?.role === 'admin' ? <Link to="/admin">На экран автора</Link> : undefined} />
          : <div className="learn-cards">{courses.map((c) => <CourseCard key={c.id} course={c} />)}</div>)}
      </QueryView>
    </>
  );
}
