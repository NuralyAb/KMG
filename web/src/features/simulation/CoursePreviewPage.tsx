import { IconArrowLeft } from '@tabler/icons-react';
import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { courseHref } from '@/api/client';
import { useChapter } from '@/api/queries';
import { EmptyState, QueryView } from '@/ui/states';
import '../learn/learn.css';
import './simulation.css';

/** Курс глазами ученика внутри экрана автора, в этой же вкладке. */
export default function CoursePreviewPage() {
  const { id = '' } = useParams();
  const query = useChapter(id);
  const back = `/admin/chapters/${encodeURIComponent(id)}`;
  const title = query.data?.title;
  useEffect(() => {
    if (title) document.title = `Предпросмотр: ${title}`;
  }, [title]);
  return (
    <div className="player preview">
      <header className="player-top">
        <Link to={back} className="player-back"><IconArrowLeft size={20} aria-hidden /><span>К главе</span></Link>
        <h1>{title ?? 'Предпросмотр'}</h1>
      </header>
      <QueryView query={query} rows={4}>
        {(chapter) => {
          const src = courseHref(chapter.course_url);
          return src ? <iframe title={chapter.title} src={src} allow="fullscreen" /> : <EmptyState title="Курс ещё не собран" action={<Link to={back}>К главе</Link>} />;
        }}
      </QueryView>
    </div>
  );
}
