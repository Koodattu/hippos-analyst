const horsesKey = 'hippos.saved-horses.v1';
const peopleKey = 'hippos.saved-people.v1';
const horseId = id => typeof id === 'string' && /^\d{1,30}$/.test(id);
const personKey = person => JSON.stringify([person.role, person.id]);
function validPerson(person) {
  return person && ['driver','trainer','owner','breeder'].includes(person.role)
    && typeof person.id === 'string' && person.id.length > 0 && typeof person.name === 'string';
}

function readList(storage, key, valid, identity) {
  try {
    const items = JSON.parse(storage.getItem(key) || '[]');
    if (!Array.isArray(items) || items.length > 100 || !items.every(valid)) throw Error('invalid');
    return { items: [...new Map(items.map(item => [identity(item), item])).values()], error: false };
  } catch {
    return { items: [], error: true };
  }
}

export function loadSaved(storage) {
  const {items, error} = readList(storage, horsesKey, horseId, id => id);
  return {ids: items, error};
}

export function loadPeople(storage) {
  return readList(storage, peopleKey, validPerson, personKey);
}

function writeToggle(storage, key, items, item, matches) {
  const next = items.some(matches) ? items.filter(value => !matches(value)) : [...items, item];
  if (next.length > 100) throw Error('limit');
  storage.setItem(key, JSON.stringify(next));
  return next;
}

export function toggleSaved(storage, id) {
  const current = loadSaved(storage);
  if (current.error || !horseId(id)) throw Error('storage');
  return writeToggle(storage, horsesKey, current.ids, id, value => value === id);
}

export function togglePerson(storage, person) {
  const current = loadPeople(storage);
  if (current.error || !validPerson(person)) throw Error('storage');
  return writeToggle(storage, peopleKey, current.items, person,
    value => value.role === person.role && value.id === person.id);
}
