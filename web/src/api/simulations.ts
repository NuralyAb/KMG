import { useQuery } from '@tanstack/react-query';
import { apiPath, get } from './client';
import type { RunState } from './types';

const POLL_MS = 3_000;

export type StageName = 'facts' | 'design' | 'model' | 'scene' | 'game' | 'look' | 'finish' | 'course';
export interface SimulationStage { name: StageName; state: 'wait' | 'now' | 'done' | 'failed' }
export interface SimulationRun {
  id: string; state: RunState; is_design_only: boolean; started_at: string | null; finished_at: string | null;
  stages: SimulationStage[]; retry: number; reason: string | null;
}
export interface Scene { id: string; title: string; goal: string; label: string; poster_url: string | null; player_url: string }
export interface NodeSimulations { scenes: Scene[]; run: SimulationRun | null }

export const isBuilding = (run: SimulationRun | null): run is SimulationRun => run?.state === 'queued' || run?.state === 'running';

/** Готовые сцены шага и последний запуск агента; пока агент работает, ответ обновляется сам. */
export function useNodeSimulations(chapter: string, node: string) {
  return useQuery({
    queryKey: ['chapter', chapter, 'simulations', node],
    queryFn: async ({ signal }) => (await get<NodeSimulations>(apiPath(['chapters', chapter, 'nodes', node, 'simulations']), signal)).data,
    refetchInterval: (query) => (isBuilding(query.state.data?.run ?? null) ? POLL_MS : false),
  });
}
