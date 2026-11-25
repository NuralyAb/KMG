import { useQueries } from '@tanstack/react-query';
import { apiPath, get } from '@/api/client';
import { useChapters, useHealth, useReviews, useRuns } from '@/api/queries';
import type { Publication } from '@/api/types';
import { attentionOf, type Attention } from './facts';

/** Всё, что требует внимания: слой, этапы, публикация, пакеты, запуски, программы. */
export function useAttention(): Attention[] {
  const chapters = useChapters().data ?? [];
  const reviews = useReviews().data ?? [];
  const runs = useRuns().data ?? [];
  const health = useHealth().data;
  const built = chapters.filter((c) => c.course_url);
  const states = useQueries({
    queries: built.map((c) => ({
      queryKey: ['chapter', c.id, 'publication'],
      queryFn: async ({ signal }: { signal: AbortSignal }) => (await get<Publication>(apiPath(['chapters', c.id, 'publication']), signal)).data,
    })),
  });
  const publications = built.flatMap((chapter, i) => {
    const state = states[i]?.data;
    return state ? [{ chapter, state }] : [];
  });
  return attentionOf({ chapters, reviews, runs, health, publications, now: Date.now() });
}
