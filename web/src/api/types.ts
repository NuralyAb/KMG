/** Типы контракта docs/API.md. Поля, которых может не быть в файлах конвейера, помечены как необязательные. */

export const STAGE_NAMES = ['errata', 'layer', 'routing', 'tasks', 'illustrations', 'course'] as const;
export type StageName = (typeof STAGE_NAMES)[number];
export type StageState = 'missing' | 'ready' | 'stale';
export interface Stage { name: StageName; state: StageState; updated_at: string | null }

export interface ChapterCounts {
  nodes: number; claims: number; tasks: number; illustrations: number; errata: number;
  units: number; units_covered: number; videos: number;
}

export interface ChapterCard {
  id: string; title: string; book: string; domain: string; pages: number[];
  counts: ChapterCounts;
  issues: number;
  stages: Stage[];
  cost_usd: number; tokens_in: number; tokens_out: number;
  course_url: string | null;
  active_run: string | null;
}

export interface Difficulty { primary: string; secondary: string | null }

export interface NodeRow {
  id: string; order: number; title: string; short_title: string; difficulty: Difficulty; threshold: boolean;
  pages: number[]; claims: number; tasks: number; format: string | null; needs_scan: number;
}

export interface ChapterPart { title: string; nodes: NodeRow[] }
export interface ChapterDetail extends ChapterCard { parts: ChapterPart[] }

export interface RawNodeDetail {
  node: unknown; route: RouteRow | null; tasks: Task[]; illustrations: Illustration[];
  prev: string | null; next: string | null;
}

export type RunState = 'queued' | 'running' | 'done' | 'failed' | 'cancelled';
export type RunCommand = 'build' | StageName | 'review' | 'video' | 'simulation';

export interface Run {
  id: string; command: RunCommand; chapter: string; args: Record<string, unknown>; state: RunState;
  started_at: string | null; finished_at: string | null; exit_code: number | null; log_tail: string[];
}

export interface RunRequest {
  command: RunCommand; chapter: string; limit?: number; node?: string; format?: 'short' | 'wide'; template?: string; until?: 'design';
}

export const SEVERITIES = ['critical', 'significant', 'minor'] as const;
export type Severity = (typeof SEVERITIES)[number];

export interface Remark {
  target: string; category: string; severity: Severity; problem: string; fix: string;
  page_pdf: number | null; quote: string | null;
}

export interface Review {
  package_id: string; chapter: string | null; created_at: string; remarks: Remark[]; counts: Record<Severity, number>;
}

export interface Video {
  id: string; chapter: string; title: string; format: '9:16' | '16:9'; duration_s: number; url: string;
  subtitles_url: string | null; passport: Record<string, unknown>; problems: string[];
}

export interface MetricRow {
  chapter: string; stage: string; nodes: number; llm_tokens_in: number; llm_tokens_out: number; money_usd: number;
  person_minutes: number; mentor_minutes: number; video_seconds: number; manual_share: number;
}

export interface CoverageRow {
  unit_id: string; kind: string; page_pdf: number; excerpt: string; node_ids: string[]; reason: string | null;
}

export interface ErrataRow { page: number; md: string; scan: string; kind: string; note: string | null }

export interface RouteRow {
  node_id: string; format: string; secondary_format?: string | null; video_scores?: Record<string, number>;
  hook_short?: boolean; template?: string | null; why?: string;
}

export interface TaskOption { id: string; text: string; misconception?: string | null }
export type TaskType = 'single' | 'multiple' | 'order' | 'gap' | 'calc';

export interface Task {
  id: string; type: TaskType; step_id: string; claim_ids: string[]; prompt: string; options?: TaskOption[];
  answer: string | number | Array<string | number>; tolerance?: number | null; unit?: string | null;
  explanation: string; kind?: string;
}

export interface Illustration {
  id: string; step_id: string; node_id?: string | null; file: string; url: string; frame_class: string; origin: string;
  label?: string | null; caption: string; alt: string; source?: string | null; claim_ids?: string[];
}

export interface SearchHit {
  chapter: string; node_id: string; node_title: string; claim_id: string; text: string; quote: string; page_pdf: number | null;
}

export interface Health {
  status: string; provider: string; model: string; claude_found: boolean; ffmpeg_found: boolean;
}

export interface CoverageMeta { total: number; covered: number; skipped: number }
export interface ErrataMeta { recognition: number; suspect: number }
export interface TasksMeta { total: number; by_type: Record<string, number> }
export interface PageMeta { total: number; page: number; limit: number }
export interface MetricsMeta { cost_usd: number; tokens_in: number; tokens_out: number }
