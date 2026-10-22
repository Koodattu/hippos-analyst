const key = 'hippos.saved-horses.v1';

export function loadSaved(storage) {
  try {
    const ids = JSON.parse(storage.getItem(key) || '[]');
    if (!Array.isArray(ids) || ids.length > 100 || ids.some(id => typeof id !== 'string' || !/^\d{1,30}$/.test(id))) throw Error('invalid');
    return { ids: [...new Set(ids)], error: false };
  } catch {
    return { ids: [], error: true };
  }
}

export function toggleSaved(storage, id) {
  const current = loadSaved(storage);
  if (current.error || !/^\d{1,30}$/.test(id)) throw Error('storage');
  const ids = current.ids.includes(id) ? current.ids.filter(value => value !== id) : [...current.ids, id];
  if (ids.length > 100) throw Error('limit');
  storage.setItem(key, JSON.stringify(ids));
  return ids;
}
