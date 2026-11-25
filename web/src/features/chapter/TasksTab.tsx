import { NativeSelect } from '@mantine/core';
import { IconListCheck } from '@tabler/icons-react';
import { useState } from 'react';
import { useTasks } from '@/api/queries';
import type { ChapterDetail } from '@/api/types';
import { TASK_TYPE, label } from '@/lib/labels';
import { FilterBar } from '@/ui/bits';
import { EmptyState, QueryView } from '@/ui/states';
import { TaskView } from '../tasks/TaskView';

export function TasksTab({ chapter }: { chapter: ChapterDetail }) {
  const [type, setType] = useState('');
  const [node, setNode] = useState('');
  const query = useTasks(chapter.id, type, node);
  const nodes = chapter.parts.flatMap((p) => p.nodes);
  if (chapter.counts.tasks === 0 && query.data?.data.length === 0) {
    return <EmptyState icon={<IconListCheck size={32} aria-hidden />} title="Заданий ещё нет" text="Они появятся после этапа «Задания»." />;
  }
  return (
    <QueryView query={query}>
      {({ data: tasks, meta }) => (
        <>
          <div className="toolbar">
            <FilterBar label="Тип задания" value={type} onChange={setType} options={[
              { value: '', label: 'Все типы' },
              ...Object.keys(TASK_TYPE).map((key) => ({ value: key, label: label(TASK_TYPE, key), count: meta?.by_type[key] ?? 0 })),
            ]} />
            <NativeSelect className="node-select" aria-label="Шаг" value={node} onChange={(e) => setNode(e.currentTarget.value)}
              data={[{ value: '', label: 'Все шаги' }, ...nodes.map((n) => ({ value: n.id, label: `${n.order}. ${n.short_title || n.title}` }))]} />
          </div>
          {tasks.length === 0 ? <EmptyState title="Под этот фильтр заданий нет" /> : (
            <div className="tasks" aria-busy={query.isPlaceholderData}>
              {tasks.map((task) => <TaskView key={task.id} task={task} chapter={chapter.id} hasNodeLink />)}
            </div>
          )}
        </>
      )}
    </QueryView>
  );
}
