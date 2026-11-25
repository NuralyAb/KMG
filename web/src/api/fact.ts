import { useMutation, useQuery } from '@tanstack/react-query';
import { apiPath, get, post } from './client';
import { useRefreshAll } from './queries';
import type { Run } from './types';

export interface FactChange {
  kind: 'changed' | 'added' | 'removed'; claim_id: string; node_id: string; before: string; after: string; quote: string; page_pdf: number | null;
  old_numbers: string[]; new_numbers: string[]; conflicts: string[]; is_serious: boolean;
}
export interface FactPlace { id: string; step_id: string; title: string; is_certain: boolean }
export interface FactReport {
  chapter: string; changes: FactChange[]; steps: { id: string; title: string; order: number | null }[];
  tasks: FactPlace[]; pictures: FactPlace[]; simulations: FactPlace[]; videos: FactPlace[];
  replaced: { where: string; before: string; after: string }[]; tasks_hidden: string[];
}
export interface FactEdit { claim_id: string; text: string; accept: boolean; minutes: number; reason: string }

/** Правки слоя, которые ещё не дошли до курса. */
export function usePendingFact(chapter: string) {
  return useQuery({ queryKey: ['chapter', chapter, 'fact'], retry: false, queryFn: async ({ signal }) => (await get<FactReport>(apiPath(['chapters', chapter, 'fact']), signal)).data });
}

/** Что было бы с такой правкой. На сервере ничего не меняется. */
export function useProbeFact(chapter: string) {
  return useMutation({ mutationFn: async (body: { claim_id: string; text: string }) => (await post<FactReport>(apiPath(['chapters', chapter, 'fact', 'probe']), body)).data });
}

export function useApplyFact(chapter: string) {
  const refresh = useRefreshAll();
  return useMutation({ mutationFn: async (body: FactEdit) => (await post<Run>(apiPath(['chapters', chapter, 'fact', 'apply']), body)).data, onSettled: refresh });
}
