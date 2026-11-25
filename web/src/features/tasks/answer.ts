import type { Task, TaskOption } from '@/api/types';
import { splitFormulas } from '@/lib/formula';

export interface OptionView { id: string; text: string; isRight: boolean; misconception: string | null }

const answerIds = (task: Task): string[] => (Array.isArray(task.answer) ? task.answer : [task.answer]).map(String);

/** Варианты single и multiple: верные отмечены, порядок как у ученика. */
export function choiceOptions(task: Task): OptionView[] {
  const right = new Set(answerIds(task));
  return (task.options ?? []).map((o) => ({ id: o.id, text: o.text, isRight: right.has(o.id), misconception: o.misconception ?? null }));
}

/** Шаги в верном порядке; неизвестный id виден как есть, чтобы ошибка задания не пряталась. */
export function orderedSteps(task: Task): string[] {
  const byId = new Map((task.options ?? []).map((o: TaskOption) => [o.id, o.text]));
  return answerIds(task).map((id) => byId.get(id) ?? id);
}

export type GapPiece = { kind: 'text'; value: string } | { kind: 'gap'; value: string };

const GAP = /\{\{\s*(\d+)\s*\}\}/g;

/** Пропуск внутри формулы рисует сам KaTeX рамкой: разрезать формулу на части нельзя. */
function fillMath(prompt: string, answerAt: (n: string) => string): string {
  return splitFormulas(prompt).map((piece) => {
    if (piece.kind === 'text') return piece.value;
    const filled = piece.value.replace(GAP, (_, n: string) => `\\boxed{\\text{${answerAt(n).replace(/[{}\\$]/g, '')}}}`);
    return piece.display ? `$$${filled}$$` : `\\(${filled}\\)`;
  }).join('');
}

/** Подставляет ответы в пропуски {{1}}, {{2}}. */
export function gapPieces(task: Task): GapPiece[] {
  const answers = answerIds(task);
  const answerAt = (n: string): string => answers[Number(n) - 1] ?? '…';
  const prompt = fillMath(task.prompt, answerAt);
  const pieces: GapPiece[] = [];
  let from = 0;
  for (const match of prompt.matchAll(GAP)) {
    if (match.index > from) pieces.push({ kind: 'text', value: prompt.slice(from, match.index) });
    pieces.push({ kind: 'gap', value: answerAt(match[1] ?? '') });
    from = match.index + match[0].length;
  }
  if (from < prompt.length) pieces.push({ kind: 'text', value: prompt.slice(from) });
  return pieces;
}

const precise = (value: number): string => value.toLocaleString('ru-RU', { maximumFractionDigits: 6 });

export function calcAnswer(task: Task): string {
  const value = typeof task.answer === 'number' ? precise(task.answer) : answerIds(task).join(', ');
  const tolerance = task.tolerance ? ` ± ${precise(task.tolerance)}` : '';
  return `${value}${tolerance}${task.unit ? ` ${task.unit}` : ''}`;
}
