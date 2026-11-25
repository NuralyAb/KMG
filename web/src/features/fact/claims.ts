import type { RawNodeDetail } from '@/api/types';

export interface FactClaim { id: string; text: string; quote: string; page: number | null }

const text = (value: unknown): string => (typeof value === 'string' ? value : '');

/** Утверждения сырого узла: запись без имени или текста править нельзя, она пропускается. */
export function claimsOf(detail: RawNodeDetail): FactClaim[] {
  const node = detail.node as { claims?: unknown } | null;
  const rows = Array.isArray(node?.claims) ? node.claims as Record<string, unknown>[] : [];
  return rows
    .map((row) => ({ id: text(row.id), text: text(row.text), quote: text(row.quote), page: typeof row.page_pdf === 'number' ? row.page_pdf : null }))
    .filter((claim) => claim.id !== '' && claim.text !== '');
}
