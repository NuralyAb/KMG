import { SEVERITIES, type Remark, type Severity } from '@/api/types';

export interface RemarkFilter { severity: Severity | 'all'; category: string; text: string }

const fold = (text: string): string => text.toLowerCase().replaceAll('ё', 'е');

export function filterRemarks(remarks: Remark[], filter: RemarkFilter): Remark[] {
  const needle = fold(filter.text.trim());
  return remarks.filter((r) =>
    (filter.severity === 'all' || r.severity === filter.severity)
    && (!filter.category || r.category === filter.category)
    && (!needle || fold(`${r.target} ${r.problem} ${r.fix} ${r.quote ?? ''}`).includes(needle)));
}

/** Группы идут от критических к мелким, пустые не показываются. */
export function groupBySeverity(remarks: Remark[]): { severity: Severity; remarks: Remark[] }[] {
  return SEVERITIES.map((severity) => ({ severity, remarks: remarks.filter((r) => r.severity === severity) }))
    .filter((group) => group.remarks.length > 0);
}

export function categoriesOf(remarks: Remark[]): string[] {
  return [...new Set(remarks.map((r) => r.category))].sort();
}

const MAX_BYTES = 80 * 1024 * 1024;

/** Проверка файла до отправки: сервер примет только zip до 80 МБ. Возвращает текст ошибки или null. */
export function packageProblem(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.zip')) return 'Нужен файл .zip с package.json и папкой frames.';
  if (file.size === 0) return 'Файл пустой.';
  if (file.size > MAX_BYTES) return 'Файл больше 80 МБ.';
  return null;
}
