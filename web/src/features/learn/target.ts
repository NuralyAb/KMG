/** Куда вернуться после входа: только свои адреса автора, иначе ссылка на вход увела бы на чужой сайт. */
export function safeTarget(value: string | null): string {
  if (!value || value.includes('\\') || !/^\/admin(?:[/?]|$)/.test(value)) return '/admin';
  return value;
}
