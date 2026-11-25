import { NativeSelect, TextInput } from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useChapters, useReview } from '@/api/queries';
import { SEVERITIES, type Remark, type Review } from '@/api/types';
import { counted, formatDateTime, FORMS } from '@/lib/format';
import { CATEGORY, SEVERITY, label } from '@/lib/labels';
import { FilterBar } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { RichText } from '@/ui/RichText';
import { EmptyState, QueryView } from '@/ui/states';
import { categoriesOf, filterRemarks, groupBySeverity, type RemarkFilter } from './remarks';
import { SEVERITY_VIEW } from './SeverityCounts';
import './review.css';

function RemarkItem({ remark }: { remark: Remark }) {
  return (
    <li className="remark">
      <div className="remark-side">
        <strong>{remark.target}</strong>
        <span className="muted">{label(CATEGORY, remark.category)}</span>
      </div>
      <div className="remark-main">
        <p className="prose"><RichText text={remark.problem} /></p>
        <div className="remark-fix"><span className="muted">Исправить так</span><p className="prose"><RichText text={remark.fix} /></p></div>
        {(remark.quote || remark.page_pdf !== null) && (
          <blockquote>
            {remark.quote && <p className="prose"><RichText text={remark.quote} /></p>}
            <footer className="muted">{remark.page_pdf !== null ? `стр. ${remark.page_pdf}` : 'страница не указана'}</footer>
          </blockquote>
        )}
      </div>
    </li>
  );
}

const START: RemarkFilter = { severity: 'all', category: '', text: '' };

function Remarks({ review }: { review: Review }) {
  const [filter, setFilter] = useState<RemarkFilter>(START);
  const { remarks } = review;
  if (remarks.length === 0) return <EmptyState icon={<IconCheck size={32} aria-hidden />} title="Замечаний нет" text="Модуль не нашёл расхождений с главой." />;
  const groups = groupBySeverity(filterRemarks(remarks, filter));
  return (
    <>
      <div className="toolbar remark-tools">
        <FilterBar label="Тяжесть" value={filter.severity} onChange={(severity) => setFilter({ ...filter, severity })} options={[
          { value: 'all', label: 'Все', count: remarks.length },
          ...SEVERITIES.map((s) => ({ value: s, label: SEVERITY[s], count: review.counts[s] })),
        ]} />
        <NativeSelect aria-label="Вид ошибки" value={filter.category} onChange={(e) => setFilter({ ...filter, category: e.currentTarget.value })}
          data={[{ value: '', label: 'Все виды ошибок' }, ...categoriesOf(remarks).map((c) => ({ value: c, label: label(CATEGORY, c) }))]} />
        <TextInput aria-label="Найти в замечаниях" placeholder="Найти в замечаниях" value={filter.text} onChange={(e) => setFilter({ ...filter, text: e.currentTarget.value })} />
      </div>
      {groups.length === 0 && <EmptyState title="Под фильтр ничего не попало" />}
      {groups.map((group) => (
        <section key={group.severity} className="remarks" data-tone={SEVERITY_VIEW[group.severity].tone} aria-label={SEVERITY[group.severity]}>
          <h2>{SEVERITY_VIEW[group.severity].icon}{SEVERITY[group.severity]}<span className="num muted">{group.remarks.length}</span></h2>
          <ul>{group.remarks.map((remark, i) => <RemarkItem key={`${remark.target}-${i}`} remark={remark} />)}</ul>
        </section>
      ))}
    </>
  );
}

function ReviewView({ review }: { review: Review }) {
  const chapter = useChapters().data?.find((c) => c.id === review.chapter);
  return (
    <>
      <PageHeader title={review.package_id} docTitle={`Пакет ${review.package_id}`} above={<Link to="/admin/review">Проверка пакета</Link>}
        subtitle={<>{counted(review.remarks.length, FORMS.remark)}, {formatDateTime(review.created_at)}.{' '}
          {review.chapter && <>Глава: <Link to={`/admin/chapters/${encodeURIComponent(review.chapter)}`}>{chapter?.title ?? review.chapter}</Link></>}</>} />
      <Remarks review={review} />
    </>
  );
}

export default function ReviewDetailPage() {
  const { packageId = '' } = useParams();
  const query = useReview(packageId);
  return <QueryView query={query}>{(review) => <ReviewView key={review.package_id} review={review} />}</QueryView>;
}
