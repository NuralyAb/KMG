import { Button, Tabs } from '@mantine/core';
import { IconPlayerPlay } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { courseHref } from '@/api/client';
import { useChapter } from '@/api/queries';
import type { ChapterDetail } from '@/api/types';
import { formatInt, formatMoney, formatPages, formatPercent } from '@/lib/format';
import { Facts } from '@/ui/bits';
import { PageHeader } from '@/ui/PageHeader';
import { QueryView } from '@/ui/states';
import { BuildDialog } from '../runs/BuildDialog';
import { FactTab } from '../fact/FactTab';
import { PassportTab } from '../fact/PassportTab';
import { BuildTab } from './BuildTab';
import { CoverageTab } from './CoverageTab';
import { ErrataTab } from './ErrataTab';
import { PathTab } from './PathTab';
import { PublishDialog } from './PublishDialog';
import { PicturesTab } from './PicturesTab';
import { TasksTab } from './TasksTab';
import { TrustTab } from './TrustTab';
import { VideosTab } from './VideosTab';
import './chapter.css';

const TABS = [
  ['path', 'Путь'], ['coverage', 'Покрытие'], ['errata', 'Опечатки'], ['tasks', 'Задания'], ['pictures', 'Рисунки'],
  ['videos', 'Ролики'], ['trust', 'Доверие'], ['fact', 'Живой факт'], ['passport', 'Паспорт'], ['build', 'Сборка'],
] as const;
type TabKey = (typeof TABS)[number][0];

const asTab = (value: string | null): TabKey => TABS.find(([key]) => key === value)?.[0] ?? 'path';

function ChapterFacts({ chapter }: { chapter: ChapterDetail }) {
  const { counts } = chapter;
  return (
    <Facts items={[
      { label: 'Шаги', value: formatInt(counts.nodes) },
      { label: 'Утверждения', value: formatInt(counts.claims) },
      { label: 'Покрытие', value: formatPercent(counts.units_covered, counts.units) },
      { label: 'Задания', value: formatInt(counts.tasks) },
      { label: 'Рисунки', value: formatInt(counts.illustrations) },
      { label: 'Замечания', value: formatInt(chapter.issues), tone: chapter.issues ? 'warn' : 'neutral' },
      { label: 'Расход', value: formatMoney(chapter.cost_usd) },
    ]} />
  );
}

function ChapterView({ chapter }: { chapter: ChapterDetail }) {
  const [params, setParams] = useSearchParams();
  const [isBuilding, setBuilding] = useState(false);
  const [isPublishing, setPublishing] = useState(false);
  const tab = asTab(params.get('tab'));
  const course = courseHref(chapter.course_url);
  const open = (next: string | null): void => setParams(next && next !== 'path' ? { tab: next } : {}, { replace: true });

  return (
    <>
      <PageHeader
        title={chapter.title} docTitle={chapter.title} above={<Link to="/admin/chapters">Главы</Link>}
        subtitle={`${chapter.book}. Стр. ${formatPages(chapter.pages)}. Предмет: ${chapter.domain}`}
        actions={
          <>
            {course && (
              <Button component={Link} to={`/admin/chapters/${encodeURIComponent(chapter.id)}/preview`}>
                Предпросмотр
              </Button>
            )}
            {course && <Button variant="default" onClick={() => setPublishing(true)}>{chapter.published_at ? 'Опубликован' : 'Опубликовать'}</Button>}
            <Button variant={course ? 'default' : 'filled'} leftSection={<IconPlayerPlay size={16} aria-hidden />}
              disabled={chapter.active_run !== null} onClick={() => setBuilding(true)}>
              {chapter.active_run ? 'Сборка идёт' : 'Собрать'}
            </Button>
          </>
        }
      />
      <ChapterFacts chapter={chapter} />
      <Tabs value={tab} onChange={open} keepMounted={false} mt="lg">
        <Tabs.List aria-label="Разделы главы">
          {TABS.map(([key, title]) => <Tabs.Tab key={key} value={key}>{title}</Tabs.Tab>)}
        </Tabs.List>
        <Tabs.Panel value="path"><PathTab chapter={chapter} /></Tabs.Panel>
        <Tabs.Panel value="coverage"><CoverageTab chapter={chapter} /></Tabs.Panel>
        <Tabs.Panel value="errata"><ErrataTab id={chapter.id} /></Tabs.Panel>
        <Tabs.Panel value="tasks"><TasksTab chapter={chapter} /></Tabs.Panel>
        <Tabs.Panel value="pictures"><PicturesTab id={chapter.id} /></Tabs.Panel>
        <Tabs.Panel value="videos"><VideosTab chapter={chapter} /></Tabs.Panel>
        <Tabs.Panel value="trust"><TrustTab chapter={chapter} /></Tabs.Panel>
        <Tabs.Panel value="fact"><FactTab chapter={chapter} /></Tabs.Panel>
        <Tabs.Panel value="passport"><PassportTab chapter={chapter} /></Tabs.Panel>
        <Tabs.Panel value="build"><BuildTab chapter={chapter} /></Tabs.Panel>
      </Tabs>
      <PublishDialog chapter={chapter} isOpen={isPublishing} onClose={() => setPublishing(false)} />
      {isBuilding && (
        <BuildDialog isOpen command="build" target={chapter} onClose={() => setBuilding(false)} onStarted={() => open('build')} />
      )}
    </>
  );
}

export default function ChapterPage() {
  const { id = '' } = useParams();
  const query = useChapter(id);
  return <QueryView query={query} rows={6}>{(chapter) => <ChapterView chapter={chapter} />}</QueryView>;
}
