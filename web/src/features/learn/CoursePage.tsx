import { useEffect, useState, type SyntheticEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useCourse } from '@/api/queries';
import type { LearnCourse } from '@/api/types';
import { formatPercent } from '@/lib/format';
import { QueryView } from '@/ui/states';
import { courseSrc } from './progress';
import { useProgress } from './useProgress';
import './learn.css';

function showPlace(frame: Window): void {
  // маршрут тот же, меняется только хвост адреса: история переходов остаётся за самим курсом
  window.history.replaceState(window.history.state, '', `${window.location.pathname}${frame.location.hash}`);
}

/** Урок из рамки виден в адресе страницы, ссылкой на него можно поделиться. */
function follow(event: SyntheticEvent<HTMLIFrameElement>): void {
  const frame = event.currentTarget.contentWindow;
  if (!frame) return;
  showPlace(frame);
  frame.addEventListener('hashchange', () => showPlace(frame));
}

/** Вид курса, путь назад и прогресс рисует сам курс; здесь прогресс повторён только для читалки. */
function Player({ course }: { course: LearnCourse }) {
  const { done, last } = useProgress(course);
  // адрес задаётся один раз: дальше по шагам ходит сам курс
  const [src] = useState(() => courseSrc(course.id, last, window.location.hash));
  useEffect(() => {
    document.title = course.title;
  }, [course.title]);
  return (
    <div className="player">
      <header className="visually-hidden">
        <h1>{course.title}</h1>
        <p role="status">Пройдено {done} из {course.steps}, {formatPercent(done, course.steps)}</p>
      </header>
      <iframe title={course.title} src={src} allow="fullscreen" onLoad={follow} />
    </div>
  );
}

export default function CoursePage() {
  const { id = '' } = useParams();
  const query = useCourse(id);
  if (query.data) return <Player key={query.data.id} course={query.data} />;
  return <main className="player-state"><Link to="/">Мои курсы</Link><QueryView query={query} rows={4}>{() => null}</QueryView></main>;
}
