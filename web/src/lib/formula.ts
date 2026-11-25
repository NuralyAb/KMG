/** Делит текст на обычные куски и формулы: $…$, $$…$$, \(…\), \[…\]. Неполные разделители остаются текстом. */

export type Piece = { kind: 'text'; value: string } | { kind: 'math'; value: string; display: boolean };

interface Delimiter { open: string; close: string; display: boolean }

const DELIMITERS: Delimiter[] = [
  { open: '$$', close: '$$', display: true },
  { open: '\\[', close: '\\]', display: true },
  { open: '\\(', close: '\\)', display: false },
  { open: '$', close: '$', display: false },
];

/** Находит закрывающий разделитель, пропуская экранированные знаки. */
function findClose(text: string, from: number, close: string): number {
  for (let i = from; i < text.length; i += 1) {
    if (text.startsWith(close, i)) return i;
    if (text[i] === '\\') i += 1;
  }
  return -1;
}

/** Одинокий доллар перед числом — деньги, а не формула: правило как в pandoc. */
function isInlineDollar(body: string, after: string | undefined): boolean {
  if (!body || /^\s/.test(body) || /\s$/.test(body)) return false;
  if (body.includes('\n\n')) return false;
  return !(after !== undefined && /\d/.test(after));
}

function matchAt(text: string, at: number): { delimiter: Delimiter; end: number } | null {
  for (const delimiter of DELIMITERS) {
    if (!text.startsWith(delimiter.open, at)) continue;
    const start = at + delimiter.open.length;
    const end = findClose(text, start, delimiter.close);
    if (end < 0 || !text.slice(start, end).trim()) continue;
    if (delimiter.open === '$' && !isInlineDollar(text.slice(start, end), text[end + 1])) continue;
    return { delimiter, end };
  }
  return null;
}

/** Текст без разделителей формул: для заголовка вкладки браузера. */
export function plainText(text: string): string {
  return splitFormulas(text).map((piece) => piece.value).join('');
}

export function splitFormulas(text: string): Piece[] {
  const pieces: Piece[] = [];
  let plain = '';
  let at = 0;
  const flush = (): void => {
    if (plain) pieces.push({ kind: 'text', value: plain });
    plain = '';
  };
  while (at < text.length) {
    if (text[at] === '\\' && text[at + 1] === '$') {
      plain += '$';
      at += 2;
      continue;
    }
    const found = matchAt(text, at);
    if (!found) {
      plain += text[at];
      at += 1;
      continue;
    }
    flush();
    const value = text.slice(at + found.delimiter.open.length, found.end).trim();
    pieces.push({ kind: 'math', value, display: found.delimiter.display });
    at = found.end + found.delimiter.close.length;
  }
  flush();
  return pieces;
}
