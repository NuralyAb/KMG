import type { ProviderName } from '@/api/types';

export const MODEL_HINT: Record<ProviderName, string> = {
  claude_code: 'Пусто: sonnet. Для повторяемой сборки укажите полное имя, например claude-sonnet-5-5',
  anthropic: 'Полное имя, например claude-sonnet-5-5',
  openai: 'Точное имя из кабинета OpenAI',
  local: 'Как её называет сервер, например имя из ollama list',
};

/** Пустой адрес значит Ollama на этом же компьютере. */
export function isOwnComputer(url: string): boolean {
  if (!url.trim()) return true;
  try {
    const host = new URL(url.trim()).hostname;
    return host === 'localhost' || host === '[::1]' || /^127(\.\d{1,3}){3}$/.test(host);
  } catch {
    return false;
  }
}

export function needsPrice(provider: ProviderName, url: string): boolean {
  return provider === 'openai' || (provider === 'local' && !isOwnComputer(url));
}
