import type { PageState } from '@/api/types';
import type { Tone } from '@/ui/bits';

const MB = 1024 * 1024;
export const MAX_FILE_MB = 400;
export const EXTENSIONS = ['.pdf', '.docx', '.md', '.txt', '.png', '.jpg', '.jpeg'] as const;

export const PAGE_TONE: Record<PageState, Tone> = { text: 'good', doubtful: 'warn', scan: 'bad', empty: 'neutral' };

export function sizeText(bytes: number): string {
  return bytes < MB ? `${Math.max(1, Math.round(bytes / 1024)).toLocaleString('ru-RU')} КБ` : `${(bytes / MB).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} МБ`;
}

/** Что не так с файлом до отправки; null — можно отправлять. Окончательно решает сервер. */
export function fileProblem(file: Pick<File, 'name' | 'size'>): string | null {
  const name = file.name.toLowerCase();
  if (!EXTENSIONS.some((e) => name.endsWith(e))) return `Такой файл не подходит. Можно: ${EXTENSIONS.join(', ')}`;
  if (file.size === 0) return 'Файл пустой';
  if (file.size > MAX_FILE_MB * MB) return `Файл больше ${MAX_FILE_MB} МБ`;
  return null;
}

/** «5-20, 25» → [[5, 20], [25, 25]]; null — запись непонятна. */
export function parseRanges(text: string): [number, number][] | null {
  const parts = text.split(',').map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) return null;
  const found: [number, number][] = [];
  for (const part of parts) {
    const match = /^(\d{1,5})(?:\s*[-–—]\s*(\d{1,5}))?$/.exec(part);
    if (!match) return null;
    const first = Number(match[1]);
    const last = Number(match[2] ?? match[1]);
    if (first < 1 || last < first) return null;
    found.push([first, last]);
  }
  return found;
}
