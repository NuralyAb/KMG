import { IconArrowLeft } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useCourse } from '@/api/queries';
import type { LearnCourse } from '@/api/types';
import { formatPercent } from '@/lib/format';
import { Meter } from '@/ui/bits';
import { QueryView } from '@/ui/states';
import { courseSrc } from './progress';
import { useProgress } from './useProgress';
import './learn.css';

function Player({ course }: { course: LearnCourse }) {
  const { done, last } = useProgress(course);
  // адрес задаётся один раз: дальше по шагам ходит сам курс
  const [src] = useState(() => courseSrc(course.id, last));
  useEffect(() => {
    document.title = course.title;
  }, [course.title]);
  return (
    <div className="player">
      <header className="player-top">
        <Link to="/" className="player-back"><IconArrowLeft size={20} aria-hidden /><span>Курсы</span></Link>
        <h1>{course.title}</h1>
        <div className="player-progress" role="status">
          <span className="num">{done} из {course.steps}, {formatPercent(done, course.steps)}</span>
          <Meter share={course.steps > 0 ? done / course.steps : 0} />
        </div>
      </header>
      <iframe title={course.title} src={src} allow="fullscreen" />
    </div>
  );
}

export default function CoursePage() {
  const { id = '' } = useParams();
  const query = useCourse(id);
  if (query.data) return <Player key={query.data.id} course={query.data} />;
  return <main className="player-state"><Link to="/">Курсы</Link><QueryView query={query} rows={4}>{() => null}</QueryView></main>;
}
