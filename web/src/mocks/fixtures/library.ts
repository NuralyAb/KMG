import type { ModelSettings, SourceDetail, Trust } from '@/api/types';

const pages: SourceDetail['page_list'] = [
  { page: 1, state: 'text', method: 'text', chars: 1800, reasons: [] },
  { page: 2, state: 'doubtful', method: 'text', chars: 1500, reasons: ['формулы могли исказиться'] },
  { page: 3, state: 'scan', method: 'text', chars: 0, reasons: ['текста нет, только изображение'] },
];

export const sources: SourceDetail[] = [
  { id: 'src_0000000000aa', name: 'Песок.txt', kind: 'txt', bytes: 52_000, added_at: '2026-11-25T10:00:00Z', state: 'ready', run: null, pages: 3,
    counts: { text: 1, doubtful: 1, scan: 1, empty: 0 }, chapters: [], page_list: pages },
  { id: 'src_0000000000bb', name: 'Камни.pdf', kind: 'pdf', bytes: 5_200_000, added_at: '2026-11-24T10:00:00Z', state: 'ready', run: null, pages: 1,
    counts: { text: 1, doubtful: 0, scan: 0, empty: 0 }, chapters: ['demo_sand'], page_list: pages.slice(0, 1) },
];

export const pageText = 'Песок в банке. <b>Не разметка</b>';

export const model: ModelSettings = {
  provider: 'claude_code', model: null, base_url: null, price_in: null, price_out: null, budget_usd: null, context: null, origin: 'env',
  keys: { anthropic: false, openai: false, local: false },
};

export const trust: Trust = {
  audit: {
    claims: 12, needs_scan: 1, by_model: 2, by_flag: { direction: 1 }, early_terms: [],
    flagged: [{ claim_id: 'demo.pores#c1', node_id: 'demo.pores', text: 'Доля пустот растёт.', quote: 'доля пустот падает', page_pdf: 9, flags: ['direction'] }],
    sensitivity: { made: 10, caught: 7, recall: 0.7, kinds: { sign_flip: { made: 10, caught: 7 } } },
  },
  audit_stale: true, verify: null, verify_stale: false,
};
