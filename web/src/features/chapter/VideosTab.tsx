import { Button } from '@mantine/core';
import { IconAlertTriangle, IconCheck, IconPlayerPlay, IconVideo } from '@tabler/icons-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { courseHref } from '@/api/client';
import { useVideos } from '@/api/queries';
import type { ChapterDetail, Video } from '@/api/types';
import { formatDuration } from '@/lib/format';
import { Chip } from '@/ui/bits';
import { RichText } from '@/ui/RichText';
import { EmptyState, QueryView } from '@/ui/states';
import { BuildDialog } from '../runs/BuildDialog';
import { passportFacts } from './passport';

function VideoItem({ video }: { video: Video }) {
  const src = courseHref(video.url);
  const subtitles = courseHref(video.subtitles_url);
  const { rows, checklist } = passportFacts(video.passport);
  return (
    <article className="video" data-format={video.format}>
      <div className="video-frame">
        {src ? (
          <video controls preload="metadata" src={src} aria-label={video.title}>
            {subtitles && <track kind="subtitles" srcLang="ru" label="Русские" src={subtitles} default />}
          </video>
        ) : <p className="muted">Файл ролика недоступен</p>}
      </div>
      <div className="video-text">
        <h3><RichText text={video.title} /></h3>
        <div className="chips">
          <Chip>{video.format === '9:16' ? 'шортс 9:16' : 'разбор 16:9'}</Chip>
          <Chip>{formatDuration(video.duration_s)}</Chip>
          {checklist && <Chip tone={checklist.failed ? 'bad' : 'good'} icon={checklist.failed ? <IconAlertTriangle aria-hidden /> : <IconCheck aria-hidden />}>физика: {checklist.passed} из {checklist.total}</Chip>}
        </div>
        {video.problems.length > 0 && (
          <div className="note" data-tone="warn">
            <IconAlertTriangle size={20} aria-hidden />
            <div><strong>Проблемы ролика</strong><ul className="list">{video.problems.map((p, i) => <li key={i}><RichText text={p} /></li>)}</ul></div>
          </div>
        )}
        {rows.length > 0 && (
          <details className="more">
            <summary>Паспорт ролика</summary>
            <dl className="pairs">{rows.map((row) => <div key={row.title}><dt>{row.title}</dt><dd className="prose"><RichText text={row.text} /></dd></div>)}</dl>
          </details>
        )}
      </div>
    </article>
  );
}

export function VideosTab({ chapter }: { chapter: ChapterDetail }) {
  const query = useVideos(chapter.id);
  const [, setParams] = useSearchParams();
  const [isOpen, setOpen] = useState(false);
  const nodes = chapter.parts.flatMap((p) => p.nodes).map((n) => ({ id: n.id, title: `${n.order}. ${n.short_title || n.title}` }));
  const action = (
    <Button variant="default" leftSection={<IconPlayerPlay size={16} aria-hidden />} disabled={chapter.active_run !== null || nodes.length === 0}
      onClick={() => setOpen(true)}>Собрать ролик</Button>
  );
  return (
    <>
      <QueryView query={query}>
        {(videos) => videos.length === 0
          ? <EmptyState icon={<IconVideo size={32} aria-hidden />} title="Роликов ещё нет" text="Ролик собирается по одному шагу: сценарий, кадры из модели, озвучка и паспорт." action={action} />
          : <><div className="toolbar">{action}</div><div className="videos">{videos.map((v) => <VideoItem key={v.id} video={v} />)}</div></>}
      </QueryView>
      {isOpen && (
        <BuildDialog isOpen command="video" target={chapter} nodes={nodes} onClose={() => setOpen(false)}
          onStarted={() => setParams({ tab: 'build' }, { replace: true })} />
      )}
    </>
  );
}
