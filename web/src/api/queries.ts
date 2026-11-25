import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { apiPath, get, post, remove } from './client';
import type {
  ChapterCard, ChapterDetail, CoverageMeta, CoverageRow, ErrataMeta, ErrataRow, Health, Illustration, MetricRow, MetricsMeta, ModelChoice,
  ModelSettings, NewChapter, PageMeta, PageText, RawNodeDetail, Review, RouteRow, Run, RunRequest, SearchHit, Source, SourceDetail, Task, TasksMeta, Trust, Video,
} from './types';

const RUNS_POLL_MS = 4_000;
const HEALTH_POLL_MS = 60_000;
export const SEARCH_MIN = 2;
export const SEARCH_LIMIT = 20;

export const isActive = (run: Pick<Run, 'state'>): boolean => run.state === 'queued' || run.state === 'running';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async ({ signal }) => (await get<Health>('/api/health', signal)).data,
    refetchInterval: HEALTH_POLL_MS,
    retry: false,
  });
}

export function useChapters() {
  return useQuery({
    queryKey: ['chapters'],
    queryFn: async ({ signal }) => (await get<ChapterCard[]>('/api/chapters', signal)).data,
    refetchInterval: (query) => (query.state.data?.some((c) => c.active_run) ? RUNS_POLL_MS : false),
  });
}

export function useChapter(id: string) {
  return useQuery({
    queryKey: ['chapter', id, 'detail'],
    queryFn: async ({ signal }) => (await get<ChapterDetail>(apiPath(['chapters', id]), signal)).data,
    refetchInterval: (query) => (query.state.data?.active_run ? RUNS_POLL_MS : false),
  });
}

export function useNode(chapter: string, node: string) {
  return useQuery({
    queryKey: ['chapter', chapter, 'node', node],
    queryFn: async ({ signal }) => (await get<RawNodeDetail>(apiPath(['chapters', chapter, 'nodes', node]), signal)).data,
  });
}

export function useCoverage(id: string, isUncoveredOnly: boolean) {
  return useQuery({
    queryKey: ['chapter', id, 'coverage', isUncoveredOnly],
    queryFn: ({ signal }) =>
      get<CoverageRow[], CoverageMeta | null>(apiPath(['chapters', id, 'coverage'], { uncovered: isUncoveredOnly ? 1 : 0 }), signal),
    placeholderData: keepPreviousData,
  });
}

export function useErrata(id: string) {
  return useQuery({
    queryKey: ['chapter', id, 'errata'],
    queryFn: ({ signal }) => get<ErrataRow[], ErrataMeta | null>(apiPath(['chapters', id, 'errata']), signal),
  });
}

export function useTrust(id: string) {
  return useQuery({ queryKey: ['chapter', id, 'trust'], queryFn: async ({ signal }) => (await get<Trust>(apiPath(['chapters', id, 'trust']), signal)).data });
}

export function useRouting(id: string) {
  return useQuery({
    queryKey: ['chapter', id, 'routing'],
    queryFn: async ({ signal }) => (await get<RouteRow[]>(apiPath(['chapters', id, 'routing']), signal)).data,
  });
}

export function useTasks(id: string, type: string, node: string) {
  return useQuery({
    queryKey: ['chapter', id, 'tasks', type, node],
    queryFn: ({ signal }) => get<Task[], TasksMeta | null>(apiPath(['chapters', id, 'tasks'], { type, node }), signal),
    placeholderData: keepPreviousData,
  });
}

export function useIllustrations(id: string) {
  return useQuery({
    queryKey: ['chapter', id, 'illustrations'],
    queryFn: async ({ signal }) => (await get<Illustration[]>(apiPath(['chapters', id, 'illustrations']), signal)).data,
  });
}

export function useVideos(id: string) {
  return useQuery({
    queryKey: ['chapter', id, 'videos'],
    queryFn: async ({ signal }) => (await get<Video[]>(apiPath(['chapters', id, 'videos']), signal)).data,
  });
}

export function useSearch(q: string, chapter: string, page: number) {
  return useQuery({
    queryKey: ['search', q, chapter, page],
    queryFn: ({ signal }) => get<SearchHit[], PageMeta | null>(apiPath(['search'], { q, chapter, page, limit: SEARCH_LIMIT }), signal),
    enabled: q.trim().length >= SEARCH_MIN,
    placeholderData: keepPreviousData,
  });
}

export function useMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: ({ signal }) => get<MetricRow[], MetricsMeta | null>('/api/metrics', signal),
  });
}

export function useRuns() {
  return useQuery({
    queryKey: ['runs'],
    queryFn: async ({ signal }) => (await get<Run[]>('/api/runs', signal)).data,
    refetchInterval: (query) => (query.state.data?.some(isActive) ? RUNS_POLL_MS : false),
  });
}

export function useReviews() {
  return useQuery({
    queryKey: ['reviews'],
    queryFn: async ({ signal }) => (await get<Review[]>('/api/reviews', signal)).data,
  });
}

export function useReview(id: string) {
  return useQuery({
    queryKey: ['reviews', id],
    queryFn: async ({ signal }) => (await get<Review>(apiPath(['reviews', id]), signal)).data,
  });
}

/** После запуска, отмены или конца сборки меняются и главы, и списки запусков. */
export function useRefreshAll(): () => void {
  const client = useQueryClient();
  return () => {
    for (const key of ['runs', 'chapters', 'chapter', 'metrics', 'reviews', 'library']) void client.invalidateQueries({ queryKey: [key] });
  };
}

export function useStartRun() {
  const refresh = useRefreshAll();
  return useMutation({
    mutationFn: async (body: RunRequest) => (await post<Run>('/api/runs', body)).data,
    onSettled: refresh,
  });
}

export function useCancelRun() {
  const refresh = useRefreshAll();
  return useMutation({
    mutationFn: async (id: string) => (await post<Run>(apiPath(['runs', id, 'cancel']))).data,
    onSettled: refresh,
  });
}

// --- база знаний и модель ---

const isExtracting = (source: Pick<Source, 'state'>): boolean => source.state === 'extracting';

export function useSources() {
  return useQuery({
    queryKey: ['library', 'list'],
    queryFn: async ({ signal }) => (await get<Source[]>('/api/library', signal)).data,
    refetchInterval: (query) => (query.state.data?.some(isExtracting) ? RUNS_POLL_MS / 2 : false),
  });
}

export function useSource(id: string) {
  return useQuery({
    queryKey: ['library', 'source', id],
    queryFn: async ({ signal }) => (await get<SourceDetail>(apiPath(['library', id]), signal)).data,
    refetchInterval: (query) => (query.state.data && isExtracting(query.state.data) ? RUNS_POLL_MS / 2 : false),
  });
}

/** stamp меняется после нового извлечения, чтобы не показать прежний текст. */
export function usePageText(id: string, page: number | null, stamp: string) {
  return useQuery({
    queryKey: ['library', 'page', id, page, stamp],
    queryFn: async ({ signal }) => (await get<PageText>(apiPath(['library', id, 'pages', String(page)]), signal)).data,
    enabled: page !== null,
  });
}

export function useDomains() {
  return useQuery({ queryKey: ['domains'], queryFn: async ({ signal }) => (await get<string[]>('/api/domains', signal)).data });
}

export function useExtract(id: string) {
  const refresh = useRefreshAll();
  return useMutation({ mutationFn: async (vision: boolean) => (await post<Run>(apiPath(['library', id, 'extract']), { vision })).data, onSettled: refresh });
}

export function useCreateChapter(id: string) {
  const refresh = useRefreshAll();
  return useMutation({ mutationFn: async (body: NewChapter) => (await post<{ id: string }>(apiPath(['library', id, 'chapters']), body)).data, onSettled: refresh });
}

export function useRemoveSource() {
  const refresh = useRefreshAll();
  return useMutation({ mutationFn: async (id: string) => (await remove<{ id: string }>(apiPath(['library', id]))).data, onSettled: refresh });
}

export function useRemoveChapter() {
  const refresh = useRefreshAll();
  return useMutation({ mutationFn: async (id: string) => (await remove<{ id: string }>(apiPath(['library', 'chapters', id]))).data, onSettled: refresh });
}

export function useModel() {
  return useQuery({ queryKey: ['model'], queryFn: async ({ signal }) => (await get<ModelSettings>('/api/settings/model', signal)).data });
}

export function useSaveModel() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ModelChoice) => (await post<ModelSettings>('/api/settings/model', body)).data,
    onSuccess: (saved) => {
      client.setQueryData(['model'], saved);
      void client.invalidateQueries({ queryKey: ['health'] });
    },
  });
}
