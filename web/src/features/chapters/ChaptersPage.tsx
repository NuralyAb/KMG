import { IconBook2 } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useChapters } from '@/api/queries';
import type { ChapterCard } from '@/api/types';
import { counted, formatMoney, formatTokens, FORMS } from '@/lib/format';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { BuildDialog } from '../runs/BuildDialog';
import { ChapterEntry, ChapterStub } from './ChapterEntry';
import './chapters.css';

export const isStarted = (c: ChapterCard): boolean => c.active_run !== null || c.stages.some((s) => s.state !== 'missing');

function summary(chapters: ChapterCard[]): string {
  const cost = chapters.reduce((sum, c) => sum + c.cost_usd, 0);
  const tokens = chapters.reduce((sum, c) => sum + c.tokens_in + c.tokens_out, 0);
  const ready = chapters.filter((c) => c.course_url).length;
  return `${counted(chapters.length, FORMS.chapter)}, с готовым курсом ${ready}. Потрачено ${formatMoney(cost)}, ${formatTokens(tokens)} токенов.`;
}

function ChapterList({ chapters, onBuild }: { chapters: ChapterCard[]; onBuild: (chapter: ChapterCard) => void }) {
  const started = chapters.filter(isStarted);
  const waiting = chapters.filter((c) => !isStarted(c));
  return (
    <>
      {started.length > 0 && (
        <div className="entries">{started.map((c) => <ChapterEntry key={c.id} chapter={c} onBuild={() => onBuild(c)} />)}</div>
      )}
      {waiting.length > 0 && (
        <section className="section" aria-labelledby="waiting">
          <h2 id="waiting">Ещё не собраны</h2>
          <ul className="stubs">{waiting.map((c) => <ChapterStub key={c.id} chapter={c} onBuild={() => onBuild(c)} />)}</ul>
        </section>
      )}
    </>
  );
}

export default function ChaptersPage() {
  const query = useChapters();
  const navigate = useNavigate();
  const [target, setTarget] = useState<ChapterCard | null>(null);
  return (
    <>
      <PageHeader title="Главы" docTitle="Главы" subtitle={query.data?.length ? summary(query.data) : undefined} />
      <QueryView query={query} rows={4}>
        {(chapters) => chapters.length === 0
          ? <EmptyState icon={<IconBook2 size={32} aria-hidden />} title="Глав пока нет" text="Загрузите книгу в базу знаний и выберите в ней страницы главы." action={<Link to="/library">Открыть базу знаний</Link>} />
          : <ChapterList chapters={chapters} onBuild={setTarget} />}
      </QueryView>
      {target && (
        <BuildDialog key={target.id} isOpen command="build" onClose={() => setTarget(null)}
          target={target}
          onStarted={() => navigate(`/chapters/${encodeURIComponent(target.id)}?tab=build`)} />
      )}
    </>
  );
}
