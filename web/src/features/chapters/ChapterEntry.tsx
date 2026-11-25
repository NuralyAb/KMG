import { Button } from '@mantine/core';
import { IconAlertTriangle, IconCheck, IconExternalLink, IconPlayerPlay } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { courseHref } from '@/api/client';
import type { ChapterCard } from '@/api/types';
import { counted, formatMoney, formatPages, formatPercent, formatTokens, FORMS } from '@/lib/format';
import { Chip, Meter } from '@/ui/bits';
import { RunChip } from '../runs/RunChip';
import { StageTrack } from './StageTrack';

interface EntryProps { chapter: ChapterCard; onBuild: () => void }

const chapterPath = (id: string): string => `/admin/chapters/${encodeURIComponent(id)}`;

function Figures({ chapter }: { chapter: ChapterCard }) {
  const { counts } = chapter;
  const parts = [
    counted(counts.nodes, FORMS.node), counted(counts.claims, FORMS.claim), counted(counts.tasks, FORMS.task),
    counted(counts.illustrations, FORMS.picture), ...(counts.videos ? [counted(counts.videos, FORMS.video)] : []),
  ];
  return <p className="entry-figures num">{parts.map((part) => <span key={part}>{part}</span>)}</p>;
}

function Coverage({ chapter }: { chapter: ChapterCard }) {
  const { units, units_covered: covered } = chapter.counts;
  if (!units) return null;
  return (
    <div className="entry-coverage">
      <span>Покрытие <span className="num">{formatPercent(covered, units)}</span></span>
      <Meter share={covered / units} />
    </div>
  );
}

/** Глава в работе: слева состав и этапы, справа цена и действия. */
export function ChapterEntry({ chapter, onBuild }: EntryProps) {
  const course = courseHref(chapter.course_url);
  return (
    <article className="entry" aria-labelledby={`t-${chapter.id}`}>
      <div className="entry-main">
        <div>
          <h2 id={`t-${chapter.id}`}><Link to={chapterPath(chapter.id)}>{chapter.title}</Link></h2>
          <p className="muted">{chapter.book}. Стр.&nbsp;{formatPages(chapter.pages)}</p>
        </div>
        <Figures chapter={chapter} />
        <StageTrack stages={chapter.stages} />
      </div>
      <div className="entry-side">
        <div className="entry-cost num">
          <strong>{formatMoney(chapter.cost_usd)}</strong>
          <span className="muted">{formatTokens(chapter.tokens_in + chapter.tokens_out)} токенов</span>
        </div>
        <Coverage chapter={chapter} />
        {chapter.published_at && <div><Chip tone="good" icon={<IconCheck aria-hidden />}>Опубликован</Chip></div>}
        {chapter.issues > 0 && (
          <div><Chip tone="warn" icon={<IconAlertTriangle aria-hidden />}>{counted(chapter.issues, FORMS.issue)}</Chip></div>
        )}
        <div className="entry-actions">
          {course && (
            <Button component="a" href={course} target="_blank" rel="noopener noreferrer" rightSection={<IconExternalLink size={16} aria-hidden />}>
              Предпросмотр
            </Button>
          )}
          {chapter.active_run
            ? <Link className="entry-run" to={`${chapterPath(chapter.id)}?tab=build`}><RunChip state="running" /> журнал</Link>
            : <Button variant={course ? 'default' : 'filled'} leftSection={<IconPlayerPlay size={16} aria-hidden />} onClick={onBuild}>Собрать</Button>}
        </div>
      </div>
    </article>
  );
}

/** Глава без сборки: одна строка, чтобы не спорить по весу с готовыми. */
export function ChapterStub({ chapter, onBuild }: EntryProps) {
  return (
    <li>
      <div>
        <Link to={chapterPath(chapter.id)}>{chapter.title}</Link>
        <p className="muted">{chapter.book}. Стр.&nbsp;{formatPages(chapter.pages)}</p>
      </div>
      <Button variant="default" onClick={onBuild} aria-label={`Собрать: ${chapter.title}`}>Собрать</Button>
    </li>
  );
}
