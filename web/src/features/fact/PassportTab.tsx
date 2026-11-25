import { courseHref } from '@/api/client';
import type { ChapterDetail } from '@/api/types';
import { EmptyState } from '@/ui/states';
import './fact.css';

/** Паспорт переноса лежит рядом с курсом и считается при каждой сборке. */
export function PassportTab({ chapter }: { chapter: ChapterDetail }) {
  const course = courseHref(chapter.course_url);
  if (!course) return <EmptyState title="Курс ещё не собран" text="Паспорт появится после этапа «Курс»." />;
  const src = `${course.replace(/[^/]*$/, '')}lab.html#passport`;
  return <iframe className="passport-frame" title="Паспорт переноса" src={src} />;
}
