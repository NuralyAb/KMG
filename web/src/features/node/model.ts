/** Узел приходит «как есть» из layer.json, поэтому каждое поле проверяется, а пропуски заменяются пустыми. */

export interface TextField { text: string; byModel: boolean; isHypothesis: boolean }
export interface Claim {
  id: string; text: string; kind: string; page: number | null; pagePrint: number | null; quote: string; sourceKind: string;
  byModel: boolean; needsScan: boolean;
}
export interface LayerBlock { key: string; title: string; field: TextField }
export interface LayerNode {
  id: string; order: number; title: string; difficulty: { primary: string; secondary: string | null }; threshold: boolean;
  pages: number[]; whyHere: TextField | null; blocks: LayerBlock[]; deeper: TextField[]; claims: Claim[];
  links: { type: string; target: string }[];
  misconception: { ref: string | null; text: string; byModel: boolean } | null;
  dataBlocks: LayerBlock[];
  analogy: { text: string; breaksWhere: string; byModel: boolean } | null;
  lens: { title: string; text: string }[];
  decision: { features: string[]; rule: string; conclusion: string; counterexample: string } | null;
  examples: { page: number | null; condition: string; steps: string[]; result: string; figure: string }[];
  bookTasks: { number: string; page: number | null; text: string; figure: string }[];
  glossary: { term: string; definition: string }[];
  needsScan: { page: number | null; what: string }[];
}

type Obj = Record<string, unknown>;

const obj = (v: unknown): Obj | null => (typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Obj) : null);
const str = (v: unknown): string => (typeof v === 'string' ? v : typeof v === 'number' ? String(v) : '');
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const objects = (v: unknown): Obj[] => list(v).map(obj).filter((o): o is Obj => o !== null);

function field(v: unknown): TextField | null {
  const o = obj(v);
  const text = o ? str(o.text) : str(v);
  if (!text.trim()) return null;
  return { text, byModel: o?.by_model === true, isHypothesis: o?.hypothesis === true };
}

function blocks(source: Obj, titles: [key: string, title: string][]): LayerBlock[] {
  return titles.flatMap(([key, title]) => {
    const found = field(source[key]);
    return found ? [{ key, title, field: found }] : [];
  });
}

const fields = (v: unknown): TextField[] => list(v).map(field).filter((f): f is TextField => f !== null);

function claim(o: Obj): Claim {
  return {
    id: str(o.id), text: str(o.text), kind: str(o.kind), page: num(o.page_pdf), pagePrint: num(o.page_print), quote: str(o.quote),
    sourceKind: str(o.source_kind), byModel: o.by_model === true, needsScan: o.needs_scan === true,
  };
}

function dataBlocks(raw: unknown): LayerBlock[] {
  const o = obj(raw);
  if (!o) return [];
  const known = blocks(o, [['from_chapter', 'Что это значит в данных'], ['breaks', 'Где правило ломается']]);
  const guesses = fields(o.hypotheses).map((f, i) => ({ key: `hypothesis-${i}`, title: 'Гипотеза', field: f }));
  return [...known, ...guesses];
}

const LENS: [string, string][] = [
  ['inputs', 'Вход'], ['manual_steps', 'Ручные шаги'], ['judgment_points', 'Где решает человек'], ['time', 'Время'],
  ['typical_errors', 'Типичные ошибки'],
];

const LAYERS: [string, string][] = [
  ['topic', 'О чём шаг'], ['main', 'Главное'], ['mechanism', 'Как это устроено'], ['practice', 'На практике'], ['nuances', 'Тонкости'],
];

export function normalizeNode(raw: unknown): LayerNode | null {
  const o = obj(raw);
  if (!o || !str(o.id)) return null;
  const layers = obj(o.layers) ?? {};
  const difficulty = obj(o.difficulty) ?? {};
  const misconception = obj(o.misconception);
  const analogy = obj(o.it_analogy);
  const lens = obj(o.inefficiency_lens);
  const decision = obj(o.decision_on_data);
  const now = field(o.now_practice);
  return {
    id: str(o.id), order: num(o.order) ?? 0, title: str(o.title) || str(o.id),
    difficulty: { primary: str(difficulty.primary), secondary: str(difficulty.secondary) || null },
    threshold: o.threshold === true,
    pages: list(o.pages).filter((p): p is number => typeof p === 'number'),
    whyHere: field(o.why_here),
    blocks: [...blocks(layers, LAYERS), ...(now ? [{ key: 'now', title: 'Как делают сейчас', field: now }] : [])],
    deeper: fields(layers.deeper),
    claims: objects(o.claims).map(claim),
    links: objects(o.links).map((l) => ({ type: str(l.type), target: str(l.target) })),
    misconception: misconception && str(misconception.text)
      ? { ref: str(misconception.ref) || null, text: str(misconception.text), byModel: misconception.by_model === true } : null,
    dataBlocks: dataBlocks(o.data_meaning),
    analogy: analogy && str(analogy.text)
      ? { text: str(analogy.text), breaksWhere: str(analogy.breaks_where), byModel: analogy.by_model === true } : null,
    lens: lens ? LENS.map(([key, title]) => ({ title, text: str(lens[key]) })).filter((row) => row.text) : [],
    decision: decision && str(decision.rule)
      ? { features: list(decision.features).map(str).filter(Boolean), rule: str(decision.rule), conclusion: str(decision.conclusion),
          counterexample: str(decision.counterexample) } : null,
    examples: objects(o.worked_examples).map((e) => ({
      page: num(e.page_pdf), condition: str(e.condition), steps: list(e.steps).map(str).filter(Boolean), result: str(e.result),
      figure: str(e.figure),
    })),
    bookTasks: objects(o.book_tasks).map((t) => ({ number: str(t.number), page: num(t.page_pdf), text: str(t.text), figure: str(t.figure) })),
    glossary: objects(o.glossary).map((g) => ({ term: str(g.term), definition: str(g.definition) })).filter((g) => g.term),
    needsScan: objects(o.needs_scan).map((s) => ({ page: num(s.page), what: str(s.what) })),
  };
}
