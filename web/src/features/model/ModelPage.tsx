import { Button, NativeSelect, NumberInput, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertTriangle, IconCloudUpload, IconDeviceDesktop } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { errorMessage } from '@/api/client';
import { useModel, useSaveModel } from '@/api/queries';
import { PROVIDERS, type ModelChoice, type ModelSettings, type ProviderName } from '@/api/types';
import { PROVIDER } from '@/lib/labels';
import { PageHeader } from '@/ui/PageHeader';
import { QueryView } from '@/ui/states';
import { isOwnComputer, MODEL_HINT, needsPrice } from './model';
import './model.css';

const KEY_VARIABLE: Partial<Record<ProviderName, string>> = { anthropic: 'ANTHROPIC_API_KEY', openai: 'OPENAI_API_KEY' };
const asNumber = (value: number | string): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null);
const knownProvider = (value: string): ProviderName => PROVIDERS.find((p) => p === value) ?? 'claude_code';

function ModelForm({ settings }: { settings: ModelSettings }) {
  const save = useSaveModel();
  const [provider, setProvider] = useState<ProviderName>(knownProvider(settings.provider));
  const [model, setModel] = useState(settings.model ?? '');
  const [url, setUrl] = useState(settings.base_url ?? '');
  const [priceIn, setPriceIn] = useState<number | string>(settings.price_in ?? '');
  const [priceOut, setPriceOut] = useState<number | string>(settings.price_out ?? '');
  const [budget, setBudget] = useState<number | string>(settings.budget_usd ?? '');
  const [context, setContext] = useState<number | string>(settings.context ?? '');

  const isLocal = provider === 'local';
  const stays = isLocal && isOwnComputer(url);
  const withPrice = needsPrice(provider, url);
  const variable = KEY_VARIABLE[provider];

  const change = (next: ProviderName): void => {
    setProvider(next);
    setModel(next === settings.provider ? settings.model ?? '' : '');
    save.reset();
  };

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    const body: ModelChoice = {
      provider, model: model.trim() || null, base_url: isLocal ? url.trim() || null : null,
      price_in: withPrice ? asNumber(priceIn) : null, price_out: withPrice ? asNumber(priceOut) : null,
      budget_usd: asNumber(budget), context: isLocal ? asNumber(context) : null,
    };
    save.mutate(body, { onSuccess: () => notifications.show({ message: 'Модель сохранена: новые сборки пойдут через неё' }) });
  };

  return (
    <form className="model-form" onSubmit={submit}>
      <NativeSelect label="Кто отвечает" value={provider} onChange={(e) => change(knownProvider(e.currentTarget.value))} data={PROVIDERS.map((p) => ({ value: p, label: PROVIDER[p] }))} />
      <TextInput label="Имя модели" description={MODEL_HINT[provider]} value={model} onChange={(e) => setModel(e.currentTarget.value)} required={provider === 'openai' || isLocal} maxLength={200} />
      {isLocal && <TextInput label="Адрес сервера" description="Пусто: Ollama на этом компьютере" placeholder="http://127.0.0.1:11434/v1" value={url} onChange={(e) => setUrl(e.currentTarget.value)} maxLength={300} />}
      {isLocal && <NumberInput label="Контекст, токенов" description="Как настроен сервер. Нужен, чтобы заметить обрезанную главу" required min={1024} max={10_000_000} allowDecimal={false} value={context} onChange={setContext} />}
      {withPrice && <NumberInput label="Цена входа, $ за млн токенов" required min={0} max={10_000} decimalSeparator="," value={priceIn} onChange={setPriceIn} />}
      {withPrice && <NumberInput label="Цена выхода, $ за млн токенов" required min={0} max={10_000} decimalSeparator="," value={priceOut} onChange={setPriceOut} />}
      <NumberInput label="Потолок одного запуска, $" description="Пусто: 25" min={0.01} max={1000} decimalSeparator="," value={budget} onChange={setBudget} />
      <div className="note model-wide" data-tone={stays ? 'good' : 'warn'}>
        {stays ? <IconDeviceDesktop size={20} aria-hidden /> : <IconCloudUpload size={20} aria-hidden />}
        <div>{stays ? 'Текст книги останется на этом компьютере.' : 'Текст книги уйдёт на сервер модели. Проверьте, что это разрешено правообладателем и вашими правилами.'}</div>
      </div>
      {variable && !settings.keys[provider] && (
        <div className="note model-wide" data-tone="bad">
          <IconAlertTriangle size={20} aria-hidden />
          <div>Ключа нет. Задайте переменную среды <code>{variable}</code> и перезапустите сервер: в браузере ключи не вводятся и не хранятся.</div>
        </div>
      )}
      {save.isError && <p role="alert" className="model-wide model-bad">{errorMessage(save.error)}</p>}
      <div className="model-wide"><Button type="submit" loading={save.isPending}>Сохранить</Button></div>
    </form>
  );
}

export default function ModelPage() {
  const query = useModel();
  return (
    <>
      <PageHeader title="Модель" docTitle="Модель" subtitle="Через неё идут сборка курса, проверка пакетов и чтение сканов. Смена модели начинает новый кэш: глава оплачивается заново." />
      <QueryView query={query} rows={4}>{(settings) => <ModelForm settings={settings} />}</QueryView>
    </>
  );
}
