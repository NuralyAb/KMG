// Сцена-вариант: "extends" берёт основу, объекты сливаются, "ключ!" заменяет объект целиком.
const isObj = x => x && typeof x === 'object' && !Array.isArray(x);
function merge(a, b) {
  const o = { ...a };
  for (const k in b) {
    if (k.endsWith('!')) o[k.slice(0, -1)] = b[k];
    else o[k] = isObj(a[k]) && isObj(b[k]) ? merge(a[k], b[k]) : b[k];
  }
  return o;
}
export function resolve(all, name, seen = []) {
  const s = all[name];
  if (!s) throw new Error('нет сцены ' + name);
  if (!s.extends) return s;
  if (seen.includes(name)) throw new Error('цикл extends');
  const { extends: base, ...rest } = s;
  return merge(resolve(all, base, [...seen, name]), rest);
}
