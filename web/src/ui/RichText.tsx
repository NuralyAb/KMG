import katex from 'katex';
import 'katex/dist/katex.min.css';
import { memo, useMemo } from 'react';
import { splitFormulas } from '@/lib/formula';
import { highlight } from '@/lib/highlight';

interface RichTextProps { text: string; query?: string }

/** Единственное место с HTML-вставкой: разметку строит сам KaTeX, trust выключен, ошибки не роняют экран. */
function Formula({ tex, display }: { tex: string; display: boolean }) {
  const html = useMemo(
    () => katex.renderToString(tex, { displayMode: display, throwOnError: false, strict: 'ignore', trust: false }),
    [tex, display],
  );
  return <span className={display ? 'formula-block' : 'formula'} dangerouslySetInnerHTML={{ __html: html }} />;
}

/** Текст главы: формулы рисует KaTeX, всё остальное React экранирует сам. */
export const RichText = memo(function RichText({ text, query = '' }: RichTextProps) {
  const pieces = useMemo(() => splitFormulas(text), [text]);
  return (
    <>
      {pieces.map((piece, i) => {
        if (piece.kind === 'math') return <Formula key={i} tex={piece.value} display={piece.display} />;
        if (!query) return <span key={i}>{piece.value}</span>;
        return highlight(piece.value, query).map((chunk, j) =>
          chunk.hit ? <mark key={`${i}-${j}`}>{chunk.text}</mark> : <span key={`${i}-${j}`}>{chunk.text}</span>);
      })}
    </>
  );
});
