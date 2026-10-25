export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function localDay(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Helsinki', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
  return ['year', 'month', 'day'].map(type => parts.find(p => p.type === type).value).join('-');
}

export function addDays(day, count) {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + count);
  return date.toISOString().slice(0, 10);
}

export function route(name, params = {}) {
  return `#/${name}${Object.keys(params).length ? '?' + new URLSearchParams(params) : ''}`;
}

export function parseRoute(hash) {
  const [name, query = ''] = hash.replace(/^#\/?/, '').split('?');
  return { name: name || 'calendar', params: Object.fromEntries(new URLSearchParams(query)) };
}

// Filtering, paging and race selection update the current view in place.
// Opening another entity is a new page, even when it shares a route name.
export function sameView(previous, next) {
  if (!previous || previous.name !== next.name) return false;
  const keys = {horse:['id'], track:['id'], person:['id','role'], party:['id','role'],
    race:['date','track'], meeting:['date','track']}[next.name] || [];
  return keys.every(key => previous.params[key] === next.params[key]);
}

export function returnContext(hash, depth = 3) {
  const {name,params} = parseRoute(hash);
  if (params.returnTo) {
    if (depth > 1) params.returnTo = returnContext(params.returnTo, depth - 1);
    else delete params.returnTo;
  }
  return route(name,params);
}

export function raceOrder(params) {
  return params.order === 'result' ? 'result' : 'program';
}

export function withRaceOrder(hash, order) {
  const { name, params } = parseRoute(hash);
  return route(name, { ...params, order: raceOrder({ order }) });
}

export function horseReturnRoute(returnTo) {
  if (typeof returnTo === 'string' && returnTo.startsWith('#/')) {
    const target = parseRoute(returnTo);
    if (['horses', 'horse', 'calendar', 'race', 'saved', 'people', 'person', 'party', 'tracks', 'track'].includes(target.name)) return target;
  }
  return { name: 'horses', params: {} };
}

export function personReturnRoute(returnTo, role) {
  if (typeof returnTo === 'string' && returnTo.startsWith('#/')) {
    const target = parseRoute(returnTo);
    if (['people', 'person', 'party', 'horse', 'race', 'calendar', 'saved'].includes(target.name)) return target;
  }
  return { name: 'people', params: { role } };
}

export function personReference(entry, role) {
  const id = String(entry[`${role}Id`] ?? '').trim();
  return ['driver', 'trainer'].includes(role) && id && id !== '0' ? { role, id } : null;
}

export function dateRange(params, overview, today) {
  if (params.from && params.to) return { from: params.from, to: params.to };
  if (params.range === 'all' && overview.first_date) return { from: overview.first_date, to: overview.last_date };
  return { from: addDays(today, -1), to: addDays(today, 6) };
}

export function calendarSelection(meetings, params, today) {
  const meeting = meetings.find(m => m.date === params.day && m.track === params.course)
    || meetings.find(m => m.date >= today)
    || meetings.at(-1);
  if (!meeting) return null;
  const race = meeting.races.find(r => r.number === params.number) || meeting.races[0];
  return { meeting, number: race?.number };
}

export function calendarParams(params, meeting, number) {
  const result = { ...params, day: meeting.date, course: meeting.track };
  if (number) result.number = number;
  else delete result.number;
  return result;
}

export function calendarPage(params, range, offset) {
  // Pin the range so newly collected dates cannot move the page on refresh.
  return { from: range.from, to: range.to, track: params.track || '',
    offset: String(offset), order: raceOrder(params),
    ...(params.sort ? {sort:params.sort,dir:params.dir || 'asc'} : {}) };
}

export function hasResult(entry) {
  return !entry.absent && !['', '0'].includes(String(entry.placing ?? '').trim());
}

export function resultText(entry, field, missing = '—') {
  if (!hasResult(entry)) return missing;
  const value = entry[field];
  return value === null || value === undefined || value === '' ? missing : String(value);
}

export function isWinner(entry) {
  // Accept an explicit first place or Hippos's equality suffix, never codes or scratches.
  return hasResult(entry) && /^1=?$/.test(String(entry.placing).trim());
}

export function nextSort(params, key) {
  if (params.sort !== key) return { sort: key, dir: 'asc' };
  return params.dir === 'desc' ? { sort: '', dir: '' } : { sort: key, dir: 'desc' };
}

export function numericValue(value) {
  const match = String(value ?? '').trim().match(/^(\d+(?:[.,]\d+)?)(?:[a-zA-Z]|=)*$/);
  return match ? Number(match[1].replace(',', '.')) : null;
}

export function orderEntries(entries, order, form = {}, toto = null) {
  const params = typeof order === 'object' ? order : { sort: order === 'result' ? 'placing' : 'number', dir: 'asc' };
  const resultNumber = (entry, key) => hasResult(entry) ? numericValue(entry[key]) : null;
  const fields = {
    number: entry => numericValue(entry.programNumber), name: entry => entry.horseName,
    driver: entry => entry.driverName || null, trainer: entry => entry.trainerName || null,
    distance: entry => numericValue(entry.distance), odds: entry => numericValue(runnerMarket(entry, toto).value),
    placing: entry => resultNumber(entry, 'placing'),
    time: entry => resultNumber(entry, entry.shortKilometerTime ? 'shortKilometerTime' : 'kilometerTime'),
    prize: entry => resultNumber(entry, 'price'),
    form: entry => form[entry.horseId]?.[0] ? resultNumber(form[entry.horseId][0].data, 'placing') : null,
  };
  const value = fields[params.sort] || fields.number;
  const collator = new Intl.Collator('fi', { numeric: true, sensitivity: 'base' });
  return [...entries].sort((a, b) => {
    const x = value(a), y = value(b);
    const compared = x == null || y == null ? Number(x == null) - Number(y == null)
      : (typeof x === 'number' ? x - y : collator.compare(x, y)) * (params.dir === 'desc' ? -1 : 1);
    return compared || Number(a.programNumber) - Number(b.programNumber) || String(a.horseId).localeCompare(String(b.horseId));
  });
}

export function calendarRaceRoute(params) {
  return route('calendar', { from: params.date, to: params.date, day: params.date,
    course: params.track, number: params.number,
    ...(params.order ? {order:params.order} : {}),
    ...(params.sort ? {sort:params.sort,dir:params.dir || 'asc'} : {}),
    ...(params.returnTo ? {returnTo:returnContext(params.returnTo)} : {}) });
}

export function historyStats(starts) {
  const entries = starts.map(s => s.data);
  return { starts: entries.length, results: entries.filter(hasResult).length, wins: entries.filter(isWinner).length };
}

export function kilometerTime(entry, missing = '—') {
  return resultText(entry, entry.shortKilometerTime ? 'shortKilometerTime' : 'kilometerTime', missing);
}

export function splitStarts(starts, today) {
  const upcoming = [], history = [];
  for (const start of starts) {
    (start.date >= today && !hasResult(start.data) ? upcoming : history).push(start);
  }
  upcoming.sort((a, b) => a.date.localeCompare(b.date) || Number(a.race_number) - Number(b.race_number));
  return { upcoming, history };
}

export function coverageState(day) {
  if (day.fetched_at === null) return 'notCollected';
  if (!day.meetings) return 'emptyCalendar';
  if (day.missing_lists || day.fields < day.races) return 'partialCollection';
  return day.races ? 'completeCollection' : 'emptyRaceLists';
}

// Provider observations stay separate; a missing new quote never revives an old one.
export function quotedOdds(value) {
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  if (typeof value === 'string' && !/^\d+(?:\.\d+)?$/.test(value)) return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 1 ? number : null;
}

export function runnerMarket(entry, toto) {
  const runner = toto?.match_status === 'matched'
    ? toto.runners.find(r => r.horse_id === entry.horseId && r.startNumber === String(entry.programNumber)) : null;
  if (runner && toto.observations.length) {
    const history = toto.observations.map(observation => {
      const quote = observation.data.odds.find(r => r.horse_id === entry.horseId && r.number === String(entry.programNumber));
      return { value: quote && !runner.scratched ? quotedOdds(quote.probable / 100) : null,
        observedAt: observation.observed_at, sourceAt: observation.data.updated, phase: observation.phase };
    });
    return { source:'Veikkaus', value:history[0].value, history, runner };
  }
  return { source:'Hippos', value:entry.absent ? null : quotedOdds(entry.winOdds), history:[], runner };
}

export function equipmentCodes(entry) {
  const yesNo = value => value === 'K' ? true : value === 'E' ? false : null;
  return { front:yesNo(entry.shoesFront), rear:yesNo(entry.shoesBack), american:yesNo(entry.americanSulkyKEX) };
}
