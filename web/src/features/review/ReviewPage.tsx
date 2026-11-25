import { IconCheck, IconChevronRight, IconShieldCheck } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { isActive, useChapters, useReviews, useRuns } from '@/api/queries';
import type { Review, Run } from '@/api/types';
import { formatDateTime } from '@/lib/format';
import { PageHeader } from '@/ui/PageHeader';
import { EmptyState, QueryView } from '@/ui/states';
import { RunLog } from '../runs/RunLog';
import { SeverityCounts } from './SeverityCounts';
import { UploadPanel } from './UploadPanel';
import './review.css';

function ReviewList({ reviews }: { reviews: Review[] }) {
  const chapters = useChapters().data ?? [];
  const sorted = [...reviews].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (
    <ul className="packages">
      {sorted.map((review) => (
        <li key={review.package_id}>
          <Link to={`/admin/review/${encodeURIComponent(review.package_id)}`}>
            <span className="package-main">
              <strong>{review.package_id}</strong>
              <span className="muted">{chapters.find((c) => c.id === review.chapter)?.title ?? review.chapter ?? 'глава не указана'}</span>
            </span>
            <SeverityCounts counts={review.counts} />
            <span className="muted num">{formatDateTime(review.created_at)}</span>
            <IconChevronRight size={18} aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function ReviewPage() {
  const query = useReviews();
  const runs = useRuns().data ?? [];
  const [started, setStarted] = useState<Run | null>(null);
  const active = runs.find((r) => r.command === 'review' && isActive(r));
  // после перезагрузки идущая проверка находится по списку запусков и не пропадает с экрана, когда закончится
  useEffect(() => {
    if (active) setStarted((prev) => prev ?? active);
  }, [active]);
  const packageId = started?.args.package_id;
  const isDone = runs.some((r) => r.id === started?.id && r.state === 'done');
  return (
    <>
      <PageHeader title="Проверка пакета" docTitle="Проверка пакета"
        subtitle="Чужой курс сверяется с главой: механизм, знаки, условия, масштаб, кадры. Замечание всегда со страницей и правкой." />
      <UploadPanel onStarted={setStarted} />
      {started && (
        <section className="section" aria-labelledby="progress">
          <h2 id="progress">Ход проверки</h2>
          <RunLog key={started.id} run={started} />
          {isDone && typeof packageId === 'string' && (
            <div className="note" data-tone="good">
              <IconCheck size={20} aria-hidden />
              <div>Проверка закончена. <Link to={`/admin/review/${encodeURIComponent(packageId)}`}>Открыть замечания</Link></div>
            </div>
          )}
        </section>
      )}
      <section className="section" aria-labelledby="packages">
        <h2 id="packages">Проверенные пакеты</h2>
        <QueryView query={query} rows={3}>
          {(reviews) => reviews.length === 0
            ? <EmptyState icon={<IconShieldCheck size={32} aria-hidden />} title="Пакетов ещё нет" text="Загрузите zip, и ответ появится здесь." />
            : <ReviewList reviews={reviews} />}
        </QueryView>
      </section>
    </>
  );
}
