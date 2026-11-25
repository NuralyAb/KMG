import { useEffect, useMemo, useState } from 'react';
import type { LearnCourse } from '@/api/types';
import { progressKey, readProgress, type Progress } from './progress';

/** Событие storage приходит, когда курс в соседней вкладке или во вложенном окне записал новый шаг. */
export function useProgress(course: LearnCourse): Progress {
  const steps = useMemo(() => new Set(course.parts.flatMap((p) => p.steps).map((s) => s.id)), [course]);
  const [progress, setProgress] = useState(() => readProgress(course.id, steps));
  useEffect(() => {
    const read = (): void => setProgress(readProgress(course.id, steps));
    const changed = (event: StorageEvent): void => {
      if (event.key === null || event.key === progressKey(course.id)) read();
    };
    read();
    window.addEventListener('storage', changed);
    return () => window.removeEventListener('storage', changed);
  }, [course.id, steps]);
  return progress;
}
