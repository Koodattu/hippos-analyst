import { loadSaved, toggleSaved } from '../hippos_analyst/web/saved.mjs';
import { personReference, personReturnRoute, returnContext, sameView } from '../hippos_analyst/web/model.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { coverageState, hasResult, isWinner, historyStats, resultText, kilometerTime, splitStarts, orderEntries, localDay, addDays, route, parseRoute, dateRange, escapeHtml, calendarSelection, calendarParams, calendarPage, raceOrder, withRaceOrder, horseReturnRoute } from '../hippos_analyst/web/model.mjs';

test('selection, filtering and paging preserve the view; opening another entity does not', () => {
  const same = (a,b) => sameView(parseRoute(a),parseRoute(b));
  assert.equal(same('#/calendar?day=2026-10-25&course=KU&number=1', '#/calendar?day=2026-10-24&course=P&number=21'),true);
  assert.equal(same('#/calendar', '#/calendar?from=2026-09-01&to=2026-09-30'),true);
  assert.equal(same('#/race?date=2026-10-25&track=KU&number=1', '#/race?date=2026-10-25&track=KU&number=21'),true);
  assert.equal(same('#/race?date=2026-10-25&track=KU', '#/race?date=2026-10-24&track=P'),false);
  assert.equal(same('#/people?role=driver', '#/people?role=trainer&q=Korpi&offset=30'),true);
  assert.equal(same('#/person?role=trainer&id=123', '#/person?role=trainer&id=123&period=history&offset=30'),true);
  assert.equal(same('#/person?role=trainer&id=123', '#/person?role=driver&id=123'),false);
  assert.equal(same('#/horse?id=123', '#/horse?id=456'),false);
  assert.equal(same('#/horse?id=123', '#/horse?id=123&offspring_offset=30'),true);
  assert.equal(same('#/party?role=owner&id=abc', '#/party?role=breeder&id=abc'),false);
  assert.equal(same('#/horses?q=Combo', '#/horses?q=Combo&offset=30'),true);
  assert.equal(sameView(undefined,parseRoute('#/calendar')),false);
  assert.equal(same('#/horses', '#/calendar'),false);
});

test('people use role and exact string ID, never a name-based match', () => {
  const entry = {driverId:'8422289643061284860',driverName:'Nimi',trainerName:'Nimi'};
  assert.deepEqual(personReference(entry, 'driver'), {role:'driver',id:entry.driverId});
  assert.equal(personReference(entry, 'trainer'), null);
  assert.equal(personReference({driverId:'0'}, 'driver'), null);
  assert.equal(personReference({ownerId:'123'}, 'owner'), null);
});

test('people, horse and race navigation retain search, role, period and page', () => {
  const list = route('people', {role:'trainer', q:'Ääni', offset:'30'});
  assert.deepEqual(personReturnRoute(list, 'trainer'), parseRoute(list));
  const profile = route('person', {role:'trainer',id:'123',period:'history',offset:'30',returnTo:list});
  assert.deepEqual(horseReturnRoute(profile), parseRoute(profile));
  assert.deepEqual(personReturnRoute(profile, 'driver'), parseRoute(profile));
  for (const invalid of ['https://example.com', 'javascript:alert(1)', '#/unknown', undefined]) {
    assert.deepEqual(personReturnRoute(invalid, 'driver'), {name:'people',params:{role:'driver'}});
  }
});

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
  for (const invalid of [undefined, 'https://example.com', 'javascript:alert(1)', '//example.com', '#/unknown?id=1']) {
    assert.deepEqual(horseReturnRoute(invalid), {name:'horses',params:{}});
  }
});

test('pedigree and owner horse links preserve internal return context', () => {
  for (const origin of [route('horse',{id:'123',offspring_offset:'30'}), route('party',{role:'owner',id:'a'.repeat(64),offset:'30'})]) {
    assert.deepEqual(horseReturnRoute(origin), parseRoute(origin));
    assert.deepEqual(personReturnRoute(origin,'trainer'),parseRoute(origin));
  }
});

test('repeated family navigation bounds nested return URLs without losing the immediate page', () => {
  let previous = route('people',{role:'owner',q:'Ääni',offset:'30'});
  for (let n=0;n<50;n++) {
    const current = route('horse',{id:String(n),offspring_offset:'30',returnTo:returnContext(previous)});
    assert.equal(parseRoute(parseRoute(current).params.returnTo).name,parseRoute(previous).name);
    assert.ok(current.length<2000);
    previous=current;
  }
  const origin = route('party',{id:'a'.repeat(64),role:'owner',offset:'30'});
  assert.equal(returnContext(origin),origin);
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


test('coverage never calls an empty race list a collected field', () => {
  const day = { fetched_at: 100, meetings: 1, races: 0, fields: 0, missing_lists: 0 };
  assert.equal(coverageState({...day, fetched_at:null}), 'notCollected');
  assert.equal(coverageState({...day, meetings:0}), 'emptyCalendar');
  assert.equal(coverageState({...day, missing_lists:1}), 'partialCollection');
  assert.equal(coverageState(day), 'emptyRaceLists');
  assert.equal(coverageState({...day, races:2, fields:1}), 'partialCollection');
  assert.equal(coverageState({...day, races:2, fields:2}), 'completeCollection');
});

import { quotedOdds, runnerMarket, equipmentCodes } from '../hippos_analyst/web/model.mjs';

test('odds distinguish missing quotes, source units and matched identities', () => {
  for (const value of [null, undefined, '', '-', 0, '0', true, 'NaN', -1, Infinity]) assert.equal(quotedOdds(value),null);
  assert.equal(quotedOdds('2.98'),2.98);
  assert.equal(quotedOdds(1),1);
  const entry={horseId:'1234567890123456789',programNumber:'7',winOdds:'2.98',absent:false};
  const toto={match_status:'matched',runners:[{horse_id:entry.horseId,startNumber:'7',scratched:false}],observations:[
    {observed_at:100,phase:'before_scheduled_start',data:{updated:90,odds:[{number:'7',horse_id:entry.horseId,probable:1009}]}}
  ]};
  assert.equal(runnerMarket(entry,toto).value,10.09);
  assert.equal(runnerMarket(entry,toto).source,'Veikkaus');
  assert.equal(runnerMarket(entry,toto).history[0].observedAt,100);
  toto.observations[0].data.odds[0].probable=0;
  assert.equal(runnerMarket(entry,toto).value,null); // Never silently fall back to stale Hippos odds.
  toto.observations[0].data.odds[0].probable=null; // Normalized omitted quote for a scratched runner.
  toto.runners[0].scratched=true;
  assert.equal(runnerMarket(entry,toto).value,null);
  assert.equal(runnerMarket(entry,toto).source,'Veikkaus');
  toto.match_status='unmatched';
  assert.equal(runnerMarket(entry,toto).source,'Hippos');
  assert.equal(runnerMarket(entry,toto).value,2.98);
  assert.equal(runnerMarket({...entry,absent:true},null).value,null);
  toto.match_status='matched';toto.runners[0].horse_id='other';
  assert.equal(runnerMarket(entry,toto).source,'Hippos');
});

test('equipment preserves unknown codes instead of claiming no shoes or no sulky', () => {
  assert.deepEqual(equipmentCodes({shoesFront:'K',shoesBack:'E',americanSulkyKEX:'K'}),{front:true,rear:false,american:true});
  assert.deepEqual(equipmentCodes({shoesFront:'X',shoesBack:null,americanSulkyKEX:'new'}),{front:null,rear:null,american:null});
});
