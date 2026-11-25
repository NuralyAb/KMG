/** Подсветка найденного без учёта регистра и «ё», как ищет сервер. */

export interface Chunk { text: string; hit: boolean }

function fold(char: string): string {
  const lower = char.toLowerCase();
  const plain = lower === 'ё' ? 'е' : lower;
  return plain.length === 1 ? plain : char;
}

const foldAll = (text: string): string => Array.from({ length: text.length }, (_, i) => fold(text.charAt(i))).join('');

export function highlight(text: string, query: string): Chunk[] {
  const needle = foldAll(query.trim());
  if (!needle) return [{ text, hit: false }];
  const haystack = foldAll(text);
  const chunks: Chunk[] = [];
  let from = 0;
  for (let at = haystack.indexOf(needle); at >= 0; at = haystack.indexOf(needle, from)) {
    if (at > from) chunks.push({ text: text.slice(from, at), hit: false });
    chunks.push({ text: text.slice(at, at + needle.length), hit: true });
    from = at + needle.length;
  }
  if (from < text.length) chunks.push({ text: text.slice(from), hit: false });
  return chunks;
}
