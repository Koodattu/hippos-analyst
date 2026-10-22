import { loadSaved, toggleSaved } from '../hippos_analyst/web/saved.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { hasResult, isWinner, historyStats, resultText, kilometerTime, splitStarts, orderEntries, localDay, addDays, route, parseRoute, dateRange, escapeHtml, calendarSelection, calendarParams, calendarPage, raceOrder, withRaceOrder, horseReturnRoute } from '../hippos_analyst/web/model.mjs';

test('horse upcoming entries stay separate from past form and missing times stay missing', () => {
  const starts = [
    {date:'2026-10-24', data:{placing:'0',shortKilometerTime:'0'}},
    {date:'2026-10-22', data:{placing:'0'}},
    {date:'2026-10-22', data:{placing:'1=',shortKilometerTime:'16,4a'}},
    {date:'2026-10-21', data:{placing:'0',kilometerTime:'0'}},
  ];
  const groups = splitStarts(starts, '2026-10-22');
  assert.deepEqual(groups.upcoming, [starts[1], starts[0]]);
  assert.deepEqual(groups.history, [starts[2], starts[3]]);
  assert.deepEqual(historyStats(groups.history), {starts:2,results:1,wins:1});
  assert.equal(kilometerTime(starts[0].data), '—');
  assert.equal(kilometerTime(starts[2].data), '16,4a');
  assert.equal(kilometerTime({placing:'1',absent:true,kilometerTime:'17,2'}), '—');
});

test('calendar pages retain filters and sort, reset race selection, and survive reload', () => {
  const params = {range:'all', track:'H', order:'result', day:'2026-10-22', course:'H', number:'1'};
  const range = {from:'2025-01-01', to:'2026-10-29'};
  const next = calendarPage(params, range, 30);
  assert.deepEqual(next, {...range, track:'H', offset:'30', order:'result'});
  const restored = parseRoute(route('calendar', next)).params;
  assert.deepEqual(restored, next);
  assert.equal(calendarParams(restored, {date:'2025-03-01',track:'H'}, '2').offset, '30');
  assert.deepEqual(calendarPage(restored, range, 0), {...range,track:'H',offset:'0',order:'result'});
});

test('result-order URL preserves selected race and filters through a reload', () => {
  const params = { from: '2026-10-21', to: '2026-10-28', track: 'H', day: '2026-10-21', course: 'H', number: '3' };
  const restored = parseRoute(withRaceOrder(route('calendar', params), 'result'));
  assert.deepEqual(restored, { name: 'calendar', params: { ...params, order: 'result' } });
  const entries = [{programNumber:'1', placing:'9'}, {programNumber:'6', placing:'1'}];
  assert.equal(orderEntries(entries, raceOrder(restored.params))[0].programNumber, '6');
  assert.equal(raceOrder(parseRoute(withRaceOrder(route('race', {date:params.day,track:'H',number:'3'}), 'program')).params), 'program');
  assert.equal(raceOrder({order:'invalid'}), 'program');
});

test('horse return route restores Finnish search and page without allowing external destinations', () => {
  const origin = route('horses', { q:'Ääni & ääni', offset:'30' });
  const profile = parseRoute(route('horse', { id:'7616196635396808820', returnTo:origin }));
  assert.deepEqual(horseReturnRoute(profile.params.returnTo), { name:'horses', params:{q:'Ääni & ääni',offset:'30'} });
  for (const invalid of [undefined, 'https://example.com', 'javascript:alert(1)', '//example.com', '#/horse?id=1']) {
    assert.deepEqual(horseReturnRoute(invalid), {name:'horses',params:{}});
  }
});

test('calendar and race origins stay available from a horse profile', () => {
  for (const name of ['calendar', 'race']) {
    const origin = route(name, {date:'2026-10-22',track:'F',number:'1',order:'result'});
    assert.deepEqual(horseReturnRoute(origin), parseRoute(origin));
  }
});

test('upcoming zeros, missing placements and scratches are not results', () => {
  for (const entry of [{}, { placing: '0', price: '0' }, { placing: '' }, { placing: '1', absent: true }]) {
    assert.equal(hasResult(entry), false);
    assert.equal(isWinner(entry), false);
    assert.equal(resultText(entry, 'price'), '—');
  }
  assert.equal(hasResult({ placing: 'hll' }), true);
  assert.equal(resultText({ placing: '2', price: '0' }, 'price'), '0');
});

test('ties count as first places; source codes never become wins', () => {
  assert.equal(isWinner({ placing: '1=' }), true);
  assert.equal(isWinner({ placing: '1' }), true);
  for (const placing of ['10', '101', 'hll', '1a']) assert.equal(isWinner({ placing }), false);
  assert.deepEqual(historyStats([{ data: { placing: '1=' } }, { data: { placing: '0' } }, { data: { placing: '2' } }, { data: { placing: '1', absent: true } }]), { starts: 4, results: 2, wins: 1 });
});

test('result sorting keeps ties stable and puts unknown results and scratches last', () => {
  const entries = [{ programNumber: '10', placing: '0' }, { programNumber: '4', placing: '2' },
    { programNumber: '7', placing: '1=' }, { programNumber: '3', placing: '1=' },
    { programNumber: '8', placing: '1', absent: true }];
  assert.deepEqual(orderEntries(entries, 'result').map(e => e.programNumber), ['3', '7', '4', '8', '10']);
  assert.deepEqual(orderEntries(entries, 'program').map(e => e.programNumber), ['3', '4', '7', '8', '10']);
  assert.equal(entries[0].programNumber, '10');
});

test('Helsinki calendar dates stay correct around midnight and DST', () => {
  assert.equal(localDay(new Date('2026-10-24T21:30:00Z')), '2026-10-25');
  assert.equal(localDay(new Date('2026-10-25T21:30:00Z')), '2026-10-25');
  assert.equal(localDay(new Date('2026-10-25T22:30:00Z')), '2026-10-26');
  assert.equal(addDays('2026-10-25', 1), '2026-10-26');
  assert.deepEqual(dateRange({ range: 'all' }, { first_date: '2025-10-22', last_date: '2026-10-23' }, '2026-10-22'), { from: '2025-10-22', to: '2026-10-23' });
});

test('URL state preserves long horse IDs and Finnish search text', () => {
  assert.deepEqual(parseRoute(route('horse', { id: '7616196635396808820' })), { name: 'horse', params: { id: '7616196635396808820' } });
  assert.deepEqual(parseRoute(route('horses', { q: 'Ääni & ääni' })).params, { q: 'Ääni & ääni' });
});

test('source text is escaped before rendering as HTML or attributes', () => {
  assert.equal(escapeHtml('<img src=x onerror="alert(1)"> &'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp;');
  assert.equal(escapeHtml("'"), '&#39;');
});

test('calendar opens today automatically, then the nearest upcoming or latest past meeting', () => {
  const meetings = ['2026-10-21', '2026-10-22', '2026-10-25'].map(date => ({ date, track: 'H', races: [{ number: '1' }] }));
  assert.equal(calendarSelection(meetings, {}, '2026-10-22').meeting.date, '2026-10-22');
  assert.equal(calendarSelection(meetings, {}, '2026-10-23').meeting.date, '2026-10-25');
  assert.equal(calendarSelection(meetings, {}, '2026-10-30').meeting.date, '2026-10-25');
  assert.equal(calendarSelection([], {}, '2026-10-22'), null);
});

test('direct race selection stays inside the filtered meetings and handles missing fields', () => {
  const meetings = [{ date: '2026-10-22', track: 'H', races: [{ number: '1' }, { number: '10' }] },
    { date: '2026-10-22', track: 'LA', races: [] }];
  assert.equal(calendarSelection(meetings, { day: '2026-10-22', course: 'H', number: '10' }, '2026-10-22').number, '10');
  assert.equal(calendarSelection(meetings, { day: '2026-10-22', course: 'H', number: '99' }, '2026-10-22').number, '1');
  assert.equal(calendarSelection(meetings, { day: '2026-10-22', course: 'LA' }, '2026-10-22').number, undefined);
  assert.equal(calendarSelection(meetings.slice(1), { day: '2026-10-22', course: 'H', number: '10' }, '2026-10-22').meeting.track, 'LA');
});

test('switching meetings and races preserves the calendar filters and string numbers', () => {
  const filters = { range: 'all', track: 'H', from: '2026-10-01', to: '2026-10-31', number: '3' };
  const params = calendarParams(filters, { date: '2026-10-22', track: 'H' }, '10');
  assert.deepEqual(params, { ...filters, day: '2026-10-22', course: 'H', number: '10' });
  assert.equal(filters.number, '3');
  assert.equal('number' in calendarParams(params, { date: '2026-10-23', track: 'H' }), false);
});


test('saved horse IDs persist, deduplicate, reject corrupt data and preserve state on write failure', () => {
  let value = null;
  const storage = { getItem: () => value, setItem: (key, next) => { value = next; } };
  assert.deepEqual(loadSaved(storage), { ids: [], error: false });
  assert.deepEqual(toggleSaved(storage, '7616196635396808820'), ['7616196635396808820']);
  assert.deepEqual(loadSaved(storage).ids, ['7616196635396808820']);
  assert.deepEqual(toggleSaved(storage, '7616196635396808820'), []);
  value = '["123","123",12]';
  assert.equal(loadSaved(storage).error, true);
  value = '["123","123"]';
  assert.deepEqual(loadSaved(storage).ids, ['123']);
  storage.setItem = () => { throw Error('quota'); };
  assert.throws(() => toggleSaved(storage, '456'));
  assert.deepEqual(loadSaved(storage).ids, ['123']);
  value = JSON.stringify(Array.from({length:100}, (_, i) => String(i)));
  assert.throws(() => toggleSaved(storage, '101'), /limit/);
});
