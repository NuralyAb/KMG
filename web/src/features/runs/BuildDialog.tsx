import { Button, Modal, NativeSelect, NumberInput, Stack, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlayerPlay } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { errorMessage } from '@/api/client';
import { useStartRun } from '@/api/queries';
import type { RunCommand, RunRequest } from '@/api/types';
import { COMMAND } from '@/lib/labels';

export interface BuildTarget { id: string; title: string }

interface BuildDialogProps {
  target: BuildTarget; command: RunCommand; isOpen: boolean; onClose: () => void; nodes?: { id: string; title: string }[];
  onStarted?: (runId: string) => void;
}

/** Что произойдёт: команды с моделью стоят денег, человек видит это до нажатия. */
const HINT: Partial<Record<RunCommand, string>> = {
  build: 'Пройдут все этапы подряд. Модель работает платно, ответы из кэша бесплатны.',
  errata: 'Страницы главы сверяются со сканом. Этап платный.',
  layer: 'Учебный слой соберётся заново. Самый дорогой этап, после него следующие этапы устареют.',
  routing: 'Для каждого шага подбирается формат. Этап платный.',
  tasks: 'Задания по всем шагам соберутся заново. Этап платный.',
  illustrations: 'Рисунки по всем шагам соберутся заново. Этап платный.',
  course: 'Страницы курса собираются из готовых файлов. Модель не нужна, бесплатно.',
  simulation: 'Агент построит 3D-симулятор по этому шагу: замысел, модель, сцена, игра, проверка. Этап платный, потолок — 1,5 доллара по прайсу.',
  video: 'Один ролик по одному шагу: сценарий, кадры, озвучка, паспорт. Этап платный.',
};

const WITH_LIMIT: ReadonlySet<RunCommand> = new Set(['build', 'layer']);

export function BuildDialog({ target, command, isOpen, onClose, nodes = [], onStarted }: BuildDialogProps) {
  const start = useStartRun();
  const [limit, setLimit] = useState<number | string>('');
  const [node, setNode] = useState('');
  const [format, setFormat] = useState<'short' | 'wide'>('short');
  const [template, setTemplate] = useState('');
  const isVideo = command === 'video';
  const isSimulation = command === 'simulation';
  const [until, setUntil] = useState<'design' | 'all'>('design');

  const close = (): void => {
    start.reset();
    onClose();
  };

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    const body: RunRequest = {
      command, chapter: target.id,
      ...(WITH_LIMIT.has(command) && typeof limit === 'number' ? { limit } : {}),
      ...(isVideo ? { node: node || nodes[0]?.id, format, template: template.trim() } : {}),
      ...(isSimulation ? { node: nodes[0]?.id, ...(until === 'design' ? { until } : {}) } : {}),
    };
    start.mutate(body, {
      onSuccess: (run) => {
        notifications.show({ message: run.state === 'queued' ? 'Запуск поставлен в очередь' : 'Сборка запущена' });
        close();
        onStarted?.(run.id);
      },
    });
  };

  return (
    <Modal opened={isOpen} onClose={close} title={`${COMMAND[command]}: запустить?`} closeButtonProps={{ 'aria-label': 'Закрыть' }}>
      <form onSubmit={submit}>
        <Stack gap="md">
          <div>
            <p><strong>{target.title}</strong></p>
            <p className="muted">{HINT[command]}</p>
          </div>
          {WITH_LIMIT.has(command) && (
            <NumberInput label="Только первые шаги" description="Пусто: вся глава" min={1} max={200} allowDecimal={false} value={limit} onChange={setLimit} />
          )}
          {isSimulation && (
            <NativeSelect label="Докуда" value={until} onChange={(e) => setUntil(e.currentTarget.value === 'all' ? 'all' : 'design')}
              data={[{ value: 'design', label: 'Только замысел: дёшево, можно посмотреть и решить' }, { value: 'all', label: 'До конца: сцена встанет в курс' }]} />
          )}
          {isVideo && (
            <>
              <NativeSelect label="Шаг" value={node || nodes[0]?.id} onChange={(e) => setNode(e.currentTarget.value)}
                data={nodes.map((n) => ({ value: n.id, label: n.title }))} />
              <NativeSelect label="Формат" value={format} onChange={(e) => setFormat(e.currentTarget.value === 'wide' ? 'wide' : 'short')}
                data={[{ value: 'short', label: 'Шортс 9:16' }, { value: 'wide', label: 'Разбор 16:9' }]} />
              <TextInput label="Шаблон сцены" description="Имя файла из доменного пакета без .py" required pattern="[A-Za-z0-9_]+"
                placeholder="well_tool_curve" value={template} onChange={(e) => setTemplate(e.currentTarget.value)} />
            </>
          )}
          {start.isError && <p role="alert" className="text-bad">{errorMessage(start.error)}</p>}
          <div className="page-actions" style={{ justifyContent: 'flex-end' }}>
            <Button variant="default" onClick={close}>Не запускать</Button>
            <Button type="submit" loading={start.isPending} leftSection={<IconPlayerPlay size={18} />}>Запустить</Button>
          </div>
        </Stack>
      </form>
    </Modal>
  );
}
