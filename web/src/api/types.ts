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
  published_at?: string | null;
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
export type RunCommand = 'build' | StageName | 'review' | 'video' | 'simulation' | 'extract' | 'audit' | 'verify' | 'fact';

export interface Run {
  id: string; command: RunCommand; chapter: string; args: Record<string, unknown>; state: RunState;
  started_at: string | null; finished_at: string | null; exit_code: number | null; log_tail: string[];
}

export interface RunRequest {
  command: RunCommand; chapter: string; limit?: number; node?: string; format?: 'short' | 'wide'; template?: string; mutants?: boolean; until?: 'design';
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

export const PAGE_STATES = ['text', 'doubtful', 'scan', 'empty'] as const;
export type PageState = (typeof PAGE_STATES)[number];
export interface LibraryPage { page: number; state: PageState; method: string; chars: number; reasons: string[] }
export type SourceState = 'uploaded' | 'extracting' | 'ready' | 'failed';

export interface Source {
  id: string; name: string; kind: string; bytes: number; added_at: string; state: SourceState; run: string | null;
  pages: number; counts: Record<PageState, number>; chapters: string[];
}
export interface SourceDetail extends Source { page_list: LibraryPage[] }
export interface PageText { page: number; text: string }
export interface NewChapter { title: string; book: string | null; pages: [number, number][]; domain: string }

export interface Sensitivity {
  made: number; caught: number; recall: number | null; kinds: Record<string, { made: number; caught: number }>;
  controls?: { made: number; caught: number }; unchecked?: number;
}
export interface FlaggedClaim { claim_id: string; node_id: string; text: string; quote: string; page_pdf: number; flags: string[] }
export interface AuditReport {
  claims: number; needs_scan: number; by_model: number; flagged: FlaggedClaim[]; by_flag: Record<string, number>;
  early_terms: { term: string; explained_in: string; used_in: string[] }[]; sensitivity?: Sensitivity;
}
export type Verdict = 'follows' | 'partial' | 'no' | 'contradicts' | 'unchecked';
export type VerdictCounts = Record<Verdict | 'total', number>;
export interface WeakItem { id: string; text: string; verdict: Verdict; why: string; quote?: string }
export interface VerifyReport { checker: string; claims: VerdictCounts; prose: VerdictCounts; weak: WeakItem[]; sensitivity?: Sensitivity; text_chars?: Record<string, number> }
export interface Trust { audit: AuditReport | null; audit_stale: boolean; verify: VerifyReport | null; verify_stale: boolean }

export interface CourseStep { id: string; order: number; title: string; minutes: number }
export interface CoursePart { title: string; steps: CourseStep[] }
export interface LearnCourse {
  id: string; title: string; book: string; steps: number; minutes: number; tasks: number; parts: CoursePart[]; published_at: string;
}
export interface PublishCheck { code: string; text: string }
export interface Publication { published_at: string | null; is_current: boolean; problem: string | null; checks: PublishCheck[]; accepted: string[] }
export interface Me { role: 'admin' | 'learner'; protected: boolean }

export const PROVIDERS = ['claude_code', 'anthropic', 'openai', 'local'] as const;
export type ProviderName = (typeof PROVIDERS)[number];
export interface ModelChoice {
  provider: ProviderName; model: string | null; base_url: string | null; price_in: number | null; price_out: number | null;
  budget_usd: number | null; context: number | null;
}
export interface ModelSettings extends Omit<ModelChoice, 'provider'> { provider: string; origin: 'file' | 'env'; keys: Record<string, boolean> }

export interface CoverageMeta { total: number; covered: number; skipped: number }
export interface ErrataMeta { recognition: number; suspect: number }
export interface TasksMeta { total: number; by_type: Record<string, number> }
export interface PageMeta { total: number; page: number; limit: number }
export interface MetricsMeta { cost_usd: number; tokens_in: number; tokens_out: number }
