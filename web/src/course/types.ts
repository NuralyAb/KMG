/** Данные курса, как их пишет build.py в data.js. Поля, которых в слое нет, приходят пустыми. */

export interface PagedText { text: string; pages: number[] }
export interface Claim {
  id: string; text: string; quote: string; page_pdf: number; kind: string; by_model?: boolean; source_kind?: string; needs_scan?: boolean;
}
export interface Term { term: string; definition: string }
export interface Formula { tex: string; page: number; legend?: { symbol: string; meaning: string; unit?: string | null }[]; errata?: string | null }
export interface BookTable {
  title: string; page: number; header?: string[]; rows: (string | number | null)[][]; corrections?: { row: number; col: number; from: unknown; to: unknown }[];
}
export interface Picture { id: string; file: string; alt: string; caption: string; label: string; source?: string | null; width?: number; height?: number; svg?: string }
export interface Video { src: string; title: string; format?: string; label?: string; subtitles?: string | null; vtt?: string | null }
export interface Beat { kind: 'title' | 'main' | 'how'; text: string; start: number; end: number; claim_id?: string | null; page?: number | null }
export interface Narration { audio: string; duration: number; beats: Beat[] }
export interface Interactive { kind: string; params?: Record<string, unknown> }
export interface WorkedExample { condition: string; steps: string[]; result: string; page_pdf: number; figure?: string | null }
export interface BookTask { number: string; text: string; page_pdf: number; figure?: string | null }

export interface TaskOption { id: string; text: string }
export type TaskType = 'single' | 'multiple' | 'order' | 'gap' | 'calc';
export interface Task {
  id: string; type: TaskType; prompt: string; options?: TaskOption[]; answer: string | number | string[]; tolerance?: number | null; unit?: string | null;
  explanation: string; claim_ids?: string[];
}

export interface Step {
  id: string; order: number; minutes: number; title: string; short_title: string; essence: string; pages: number[]; threshold?: boolean;
  how: { title: string; by_model?: boolean; paragraphs: PagedText[] }[];
  deeper: PagedText[]; glossary: Term[]; claims: Claim[]; tasks: Task[]; pictures: Picture[]; videos: Video[]; interactive: Interactive | null; narration?: Narration | null;
  procedure: PagedText[]; numbers: { text: string; page: number }[]; formulas: Formula[]; tables: BookTable[];
  worked_examples?: WorkedExample[] | null; book_tasks?: BookTask[] | null; needs_scan?: { what: string; page: number }[] | null;
  misconception?: { text: string; by_model?: boolean } | null;
  data_meaning?: { from_chapter: { text: string; by_model?: boolean }; breaks: { text: string }; hypotheses?: { text: string }[] } | null;
  it_analogy?: { text: string; breaks_where: string } | null;
  now_practice?: { text: string } | null;
  inefficiency_lens?: { inputs?: string; manual_steps?: string; judgment_points?: string; time?: string; typical_errors?: string } | null;
  decision_on_data?: { features: string[]; rule: string; conclusion: string; counterexample?: string | null } | null;
  why_here?: { text: string } | null; format?: string | null; format_why?: string | null; links?: { type: string; target: string }[] | null;
}
export interface Part { title: string; nodes: string[] }
export interface Course { id: string; title: string; book: string; generated_by: string; parts: Part[]; steps: Step[] }

declare global {
  interface Window {
    COURSE?: Course;
    katex?: { renderToString: (code: string, options: object) => string };
    Simulations?: { mount: (root: HTMLElement) => void };
  }
}
