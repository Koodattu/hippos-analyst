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
    if (['horses', 'calendar', 'race', 'saved'].includes(target.name)) return target;
  }
  return { name: 'horses', params: {} };
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
    offset: String(offset), order: raceOrder(params) };
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

export function orderEntries(entries, order) {
  const place = entry => hasResult(entry) && /^\d+=?$/.test(String(entry.placing)) ? parseInt(entry.placing, 10) : Infinity;
  return [...entries].sort((a, b) => (order === 'result' ? place(a) - place(b) : 0) || Number(a.programNumber) - Number(b.programNumber));
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
