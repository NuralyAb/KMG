import { IconCheck } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import type { Task } from '@/api/types';
import { TASK_KIND, TASK_TYPE, label } from '@/lib/labels';
import { RichText } from '@/ui/RichText';
import { calcAnswer, choiceOptions, gapPieces, orderedSteps } from './answer';
import './tasks.css';

function Choices({ task }: { task: Task }) {
  return (
    <ul className="task-options">
      {choiceOptions(task).map((option) => (
        <li key={option.id} data-right={option.isRight || undefined}>
          <span className="task-mark">{option.isRight && <IconCheck size={16} stroke={2.6} aria-hidden />}</span>
          <div>
            <RichText text={option.text} />
            {option.isRight && <span className="visually-hidden"> (верный ответ)</span>}
            {option.misconception && <span className="muted task-misc">ловит заблуждение {option.misconception}</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}

function Answer({ task }: { task: Task }) {
  if (task.type === 'single' || task.type === 'multiple') return <Choices task={task} />;
  if (task.type === 'order') {
    return <ol className="task-order">{orderedSteps(task).map((step, i) => <li key={i}><RichText text={step} /></li>)}</ol>;
  }
  if (task.type === 'calc') {
    return <p className="task-calc"><IconCheck size={16} stroke={2.6} aria-hidden /><span>Ответ: <strong className="num"><RichText text={calcAnswer(task)} /></strong></span></p>;
  }
  return null;
}

function Prompt({ task }: { task: Task }) {
  if (task.type !== 'gap') return <RichText text={task.prompt} />;
  return (
    <>
      {gapPieces(task).map((piece, i) => piece.kind === 'gap'
        ? <strong key={i} className="task-gap"><RichText text={piece.value} /></strong>
        : <RichText key={i} text={piece.value} />)}
    </>
  );
}

/** Задание так, как его видит автор курса: верный ответ показан сразу. */
export function TaskView({ task, chapter, hasNodeLink = false }: { task: Task; chapter: string; hasNodeLink?: boolean }) {
  return (
    <article className="task">
      <p className="task-meta muted">
        <span>{label(TASK_TYPE, task.type)}</span>
        {task.kind && <span>{label(TASK_KIND, task.kind)}</span>}
        {hasNodeLink && <Link to={`/chapters/${encodeURIComponent(chapter)}/nodes/${encodeURIComponent(task.step_id)}`}>{task.step_id}</Link>}
      </p>
      <div className="task-prompt prose"><Prompt task={task} /></div>
      <Answer task={task} />
      {task.explanation && <p className="task-why prose muted"><RichText text={task.explanation} /></p>}
    </article>
  );
}
