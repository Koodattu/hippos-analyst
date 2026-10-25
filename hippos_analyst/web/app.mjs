import { loadSaved, toggleSaved } from './saved.mjs';
import { fi as t } from './locales/fi.mjs';
import { escapeHtml as e, localDay, addDays, route, parseRoute, dateRange, orderEntries, historyStats, coverageState, kilometerTime, splitStarts, isWinner, hasResult, resultText, calendarSelection, calendarParams, calendarPage, raceOrder, withRaceOrder, horseReturnRoute, personReturnRoute, personReference, returnContext, sameView, runnerMarket, equipmentCodes } from './model.mjs';

const app = document.querySelector('#app');
let overview, controller, generation = 0, currentRace, renderedRoute;
const icon = name => {
  const paths = { calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18m-13 4h2m4 0h2"/>',
    horse: '<path d="m6 21 1-7-3-3 5-6 1-3 4 3 4 1 2 6-3 3-2-2-2 3 1 5M11 8h.01"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>', back: '<path d="M19 12H5m5-5-5 5 5 5"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    external: '<path d="M14 3h7v7m0-7L10 14M10 3H4v17h17v-6"/>',
  };
  return `<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${paths[name] || paths.horse}</svg>`;
};
const link = (name, params, label, cls = '') => `<a class="${cls}" href="${e(route(name, params))}">${label}</a>`;
const dateText = (day, options = {}) => new Intl.DateTimeFormat('fi-FI', { day: 'numeric', month: 'numeric', year: 'numeric', ...options, timeZone: 'Europe/Helsinki' }).format(new Date(`${day}T12:00:00Z`));
const timestamp = value => value ? new Intl.DateTimeFormat('fi-FI', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Helsinki' }).format(new Date(value * 1000)) : t.noUpdate;
const trackName = m => m.data.formattedTrackName || m.city || m.track;
const badge = (label, cls = '') => `<span class="badge ${cls}">${e(label)}</span>`;
const source = () => `<a class="source-link" href="https://heppa.hippos.fi/heppa/app" target="_blank" rel="noreferrer">${e(t.openSource)} ${icon('external')}</a>`;
const empty = (title, hint, action = '') => `<div class="empty">${icon('search')}<h2>${e(title)}</h2>${hint ? `<p>${e(hint)}</p>` : ''}${action}</div>`;

async function api(path, params = {}) {
  const query = new URLSearchParams(params);
  query.delete('returnTo');
  const response = await fetch(`/api/${path}?${query}`, { signal: controller.signal });
  if (!response.ok) throw Object.assign(new Error('API request failed'), { status: response.status });
  return response.json();
}

function shell(name) {
  const horses = ['horses', 'horse'].includes(name);
  app.innerHTML = `<header class="app-header"><a href="#/calendar" class="brand"><span class="brand-mark">${icon('horse')}</span><span>${e(t.brand)}</span></a>
    <nav aria-label="${e(t.workspace)}">${link('calendar', {}, `${icon('calendar')}<span>${e(t.calendar)}</span>`, ['calendar', 'meeting', 'race'].includes(name) ? 'nav-link active' : 'nav-link')}${link('horses', {}, `${icon('horse')}<span>${e(t.horses)}</span>`, horses ? 'nav-link active' : 'nav-link')}${link('people', {role:'driver'}, e(t.people), ['people', 'person', 'party'].includes(name) ? 'nav-link active' : 'nav-link')}${link('saved', {}, e(t.saved), name === 'saved' ? 'nav-link active' : 'nav-link')}${link('coverage', {}, e(t.coverageTitle), name === 'coverage' ? 'nav-link active' : 'nav-link')}</nav>
    </header>
    <main id="main" tabindex="-1"><div class="loading" role="status">${e(t.loading)}</div></main>`;
}

function header(title, description = '', eyebrow = '', extra = '') {
  return `<div class="page-heading"><div>${eyebrow ? `<div class="eyebrow">${eyebrow}</div>` : ''}<h1 tabindex="-1">${e(title)}</h1>${description ? `<p>${e(description)}</p>` : ''}</div>${extra}</div>`;
}

function note(text) {
  return `<details class="data-note"><summary>${e(t.aboutData)}</summary><p>${e(text)}</p></details>`;
}

function stats(items) {
  return `<div class="stats">${items.map(([value, label]) => `<div class="stat"><strong>${e(value)}</strong><span>${e(label)}</span></div>`).join('')}</div>`;
}

function freshness(value) {
  return `<span class="freshness">${icon('clock')}${e(value ? t.updated(timestamp(value)) : t.noUpdate)}</span>`;
}

async function calendarView(params) {
  const today = localDay(new Date(overview.now));
  const range = dateRange(params, overview, today);
  const data = await api('calendar', { ...range, track: params.track || '', offset: params.offset || '0' });
  const pageLink = (offset, label) => link('calendar', calendarPage(params, range, offset), e(label), 'button calendar-page');
  const pages = data.total > data.limit ? `<nav class="pagination" aria-label="${e(t.meetingPages)}">${data.offset > 0 ? pageLink(Math.max(0, data.offset - data.limit), t.previous) : '<span></span>'}<span>${e(t.page(data.offset + 1, Math.min(data.offset + data.limit, data.total), data.total))}</span>${data.offset + data.limit < data.total ? pageLink(data.offset + data.limit, t.next) : '<span></span>'}</nav>` : '';
  const selection = calendarSelection(data.meetings, params, today);
  let detail = '';
  if (selection) {
    const { meeting: m, number } = selection;
    if (number) {
      currentRace = await api('race', { date: m.date, track: m.track, number });
      detail = raceDetail(currentRace, params, raceOrder(params));
    } else detail = `<div class="selected-heading"><h2>${e(trackName(m))}</h2><p>${e(dateText(m.date))}</p></div>${empty(t.noRaces, t.noRacesHint)}`;
  }
  const changeWeek = delta => ({ from: addDays(range.from, delta), to: addDays(range.to, delta), track: params.track || '' });
  return `<h1 class="sr-only" tabindex="-1">${e(t.calendar)}</h1>
    <form id="calendar-filter" class="filters"><div class="segmented">${link('calendar', { track: params.track || '' }, e(t.near), params.range !== 'all' && !params.from ? 'selected' : '')}${link('calendar', { from: addDays(today, -6), to: today, track: params.track || '' }, e(t.lastWeek))}${link('calendar', { range: 'all', track: params.track || '' }, e(t.archive), params.range === 'all' ? 'selected' : '')}</div>
    <label>${e(t.from)}<input name="from" type="date" value="${e(range.from)}" required></label><label>${e(t.to)}<input name="to" type="date" value="${e(range.to)}" required></label><label class="track-filter">${e(t.track)}<select name="track"><option value="">${e(t.allTracks)}</option>${Object.entries(overview.tracks).map(([code, label]) => `<option value="${e(code)}" ${code === params.track ? 'selected' : ''}>${e(label)}</option>`).join('')}</select></label><button type="submit" class="button primary">${e(t.apply)}</button></form>
    ${overview.paused ? badge(t.paused, 'warning') : overview.failed ? badge(t.failed, 'warning') : ''}
    <div class="calendar-workspace"><section class="meeting-browser" aria-label="${e(t.selectMeeting)}"><div class="meeting-browser-heading"><h2>${e(t.meetingHeading)}</h2><div>${link('calendar', changeWeek(-7), icon('back') + `<span class="sr-only">${e(t.earlier)}</span>`, 'week-arrow')}${link('calendar', changeWeek(7), icon('arrow') + `<span class="sr-only">${e(t.later)}</span>`, 'week-arrow')}</div></div>
    ${pages}<div class="meeting-list">${data.meetings.map(m => {
      const selected = selection.meeting.date === m.date && selection.meeting.track === m.track;
      const label = m.canceled ? t.canceled : m.data.hasPublishedResults ? t.results : t.racecard;
      return `<article class="meeting-card${selected ? ' selected' : ''}"><a class="meeting-select" href="${e(route('calendar', calendarParams(params, m, m.races[0]?.number)))}" ${selected ? 'aria-current="true"' : ''}><div class="meeting-meta"><strong>${e(dateText(m.date, { weekday: 'short', year: undefined }))}</strong><span>${e(m.start_time ? t.at(m.start_time.slice(0, 5)) : t.unknown)}</span></div><h3>${e(trackName(m))}</h3><p class="meeting-name">${e(m.name || t.unknown)}</p><div class="meeting-bottom">${m.canceled || m.data.hasPublishedResults ? badge(label, m.canceled ? 'warning' : 'success') : ''}${m.date === today ? badge(t.today, 'accent') : m.date === addDays(today, 1) ? badge(t.tomorrow, 'accent') : ''}<span>${e(t.fields(m.collected_races, m.race_count))}</span></div></a>
      <div class="quick-races" aria-label="${e(t.raceHeading)}">${m.races.map(r => `<a href="${e(route('calendar', calendarParams(params, m, r.number)))}" aria-label="${e(t.directRace(r.number))}" ${selected && selection.number === r.number ? 'aria-current="true"' : ''}>${e(r.number)}</a>`).join('')}</div></article>`;
    }).join('')}</div></section><section class="selected-race" id="selected-race" aria-label="${e(t.selectedMeeting)}" tabindex="-1">${data.meetings.length ? detail : empty(t.empty, t.emptyHint, link('calendar', { range: 'all', track: params.track || '' }, e(t.archive), 'button'))}</section></div>`;
}

async function coverageView(params) {
  const data = await api('coverage', { offset: params.offset || '0' });
  return `${header(t.coverageTitle, t.calendarSummary(overview.meeting_count, overview.race_count, overview.horse_count), '', freshness(overview.last_fetched_at))}
    <div class="collection-status" role="status">${e(overview.paused ? t.pausedHint : overview.failed ? t.failedHint : t.collectionHint)} ${e(t.queue(overview.pending))}</div>
    ${note(t.coverageMeaning + " " + t.sourceTime + " " + t.localHint)}${overview.toto?.targets ? `<section class="toto-coverage"><h2>${e(t.totoTitle)}</h2><p>${e(t.totoCount(overview.toto.matched, overview.toto.observations))} · ${e(t.queue(overview.toto.pending))}</p>${overview.toto.unmatched ? `<p>${e(t.totoUnmatched)}: ${overview.toto.unmatched}</p>` : ''}${freshness(overview.toto.last_fetched_at)}</section>` : ''}
    ${data.days.length ? `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.coverageTitle)}"><table><thead><tr>${[t.date, t.collectionState, t.meetingHeading, t.racecard, t.calendarUpdated].map(x => `<th scope="col">${e(x)}</th>`).join('')}</tr></thead><tbody>${data.days.map(day => `<tr><td>${link('calendar', {from:day.date,to:day.date}, e(dateText(day.date)))}</td><td>${e(t[coverageState(day)])}${day.status === 'failed' ? `<small>${e(t.failed)}</small>` : day.status === 'pending' && day.fetched_at !== null ? `<small>${e(t.refreshPending)}</small>` : ''}</td><td class="numeric">${day.fetched_at === null ? t.unknown : e(day.meetings)}</td><td>${day.fetched_at === null ? t.unknown : e(t.fields(day.fields, day.races))}${day.missing_lists ? `<small>${e(t.missingLists(day.missing_lists))}</small>` : ''}</td><td>${e(timestamp(day.fetched_at))}</td></tr>`).join('')}</tbody></table></div>` : empty(t.noCoverage, t.noCoverageHint)}
    <div class="pagination">${data.offset ? link('coverage', {offset:Math.max(0,data.offset-data.limit)}, e(t.previous), 'button') : '<span></span>'}<span>${e(t.page(data.total ? data.offset+1 : 0, Math.min(data.offset+data.limit,data.total),data.total))}</span>${data.offset+data.limit<data.total ? link('coverage',{offset:data.offset+data.limit},e(t.next),'button') : '<span></span>'}</div>`;
}

function meetingHeader(m) {
  return header(trackName(m), m.name || '', `${e(dateText(m.date, { weekday: 'long' }))} <span>·</span> ${e(m.start_time ? t.at(m.start_time.slice(0, 5)) : t.unknown)}`, source());
}

function raceMeta(r) {
  return [r.distance ? `${r.distance} m` : '', t.forms[r.start_form] || r.start_form, t.breeds[r.breed] || r.breed, r.data.monte ? t.monte : '', r.data.startType !== 'TOTO' ? t.types[r.data.startType] || r.data.startType : ''].filter(Boolean).join(' · ');
}

async function meetingView(params) {
  const { meeting: m, races } = await api('meeting', params);
  return `${link('calendar', {}, `${icon('back')}${e(t.backCalendar)}`, 'back-link')}${meetingHeader(m)}
    <div class="detail-toolbar"><div>${m.canceled ? badge(t.canceled, 'warning') : ''}${badge(t.fields(m.collected_races, m.race_count))}</div>${freshness(m.races_fetched_at)}</div>
    <div class="section-heading"><h2>${e(t.raceHeading)}</h2></div>
    <div class="race-grid">${races.map(r => link('race', { date: m.date, track: m.track, number: r.number }, `<div class="race-tile-top"><span class="race-number">${e(r.number)}</span>${badge(r.has_results ? t.results : r.field_fetched_at ? t.racecard : t.incomplete, r.has_results ? 'success' : '')}</div><h3>${e(t.race(r.number))}</h3><p>${e(raceMeta(r))}</p><div class="race-tile-bottom"><span>${r.data.plannedTime ? `${e(t.at(r.data.plannedTime))} · ` : ''}${e(r.entry_count !== null ? t.entries(r.entry_count) : t.noUpdate)}</span>${icon('arrow')}</div>`, 'race-tile')).join('')}</div>
    ${!races.length ? empty(t.noRaces, t.noRacesHint) : ''}`;
}

function recentForm(starts = []) {
  if (!starts.length) return `<span class="muted">${e(t.noPriorForm)}</span>`;
  return `<ol class="runner-form">${starts.map(s => `<li><strong class="${isWinner(s.data) ? 'form-win' : ''}">${e(s.absent ? t.absent : resultText(s.data, 'placing', t.unknown))}</strong><span title="${e(dateText(s.date))}">${e(dateText(s.date, {year: s.date.slice(0,4) === currentRace.meeting.date.slice(0,4) ? undefined : '2-digit'}))}</span>${s.data.startType && s.data.startType !== 'TOTO' ? `<small>${e(t.types[s.data.startType] || s.data.startType)}</small>` : ''}</li>`).join('')}</ol>`;
}

function equipmentText(entry) {
  const codes = equipmentCodes(entry);
  const shoes = codes.front === null || codes.rear === null ? ''
    : codes.front && codes.rear ? t.allShoes : !codes.front && !codes.rear ? t.noShoes
    : codes.front ? t.frontShoesOnly : t.rearShoesOnly;
  const cart = codes.american === null ? '' : codes.american ? t.americanCart : t.regularCart;
  return [shoes,cart].filter(Boolean).join(' · ');
}

const oddsText = value => value === null ? t.unknown : value.toLocaleString('fi-FI',{minimumFractionDigits:2,maximumFractionDigits:2});

function oddsCell(entry, toto) {
  const market = runnerMarket(entry,toto);
  const observed = market.history[0];
  const hint = observed ? `${t.totoObserved(timestamp(observed.observedAt))} · ${t.totoSourceTime(timestamp(observed.sourceAt))}` : t.oddsHint;
  return `<td class="numeric odds-cell" title="${e(hint)}"><strong>${e(oddsText(market.value))}</strong>${market.value !== null || observed ? `<small>${e(market.source)}</small>` : ''}${market.runner?.scratched && !entry.absent ? `<small class="scratch-note">${e(t.totoMismatch)}</small>` : ''}</td>`;
}

function totoStatus(toto) {
  if (!toto) return '';
  const latest = toto.observations[0];
  const label = toto.collection_failed ? t.totoFailed : toto.match_status === 'unmatched' ? t.totoUnmatched : latest
    ? `${t.totoTitle} · ${t.totoObserved(timestamp(latest.observed_at))}`
    : toto.match_status === 'pending' ? t.totoPending : t.totoNoOdds;
  return `<span class="toto-status">${e(label)}</span>`;
}

function marketHistory(id) {
  const entry = currentRace?.entries.find(r => r.horseId === id);
  if (!entry) return '';
  const market = runnerMarket(entry,currentRace.toto);
  if (!market.history.length) return '';
  return `<section class="odds-history"><h3>${e(t.oddsHistory)} · ${e(t.totoTitle)}</h3><ul>${market.history.map(item => `<li><strong>${e(oddsText(item.value))}</strong> ${e(t.totoObserved(timestamp(item.observedAt)))}<small>${e(t.totoSourceTime(timestamp(item.sourceAt)))} · ${e(item.phase === 'before_scheduled_start' ? t.totoBefore : t.totoAfter)}</small></li>`).join('')}</ul></section>`;
}

function raceTable(entries, order = 'program', form = {}, toto = null) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.racecard)}"><table><thead><tr>${[t.number, t.horse, t.priorForm, t.driver, t.distance, t.winOdds, t.placing, t.kmTime, t.prize].map(label => `<th scope="col">${e(label)}</th>`).join('')}</tr></thead><tbody>${orderEntries(entries, order).map(r => `<tr class="${r.absent ? 'scratched' : isWinner(r) ? 'winner' : ''}"><td><span class="program-number">${e(r.programNumber)}</span></td><td><a href="${e(route('horse', { id: r.horseId, returnTo: returnContext(location.hash) }))}" class="horse-name" data-preview="${e(r.horseId)}" aria-expanded="false" title="${e(t.expandHorse)}">${e(r.horseName)}<span aria-hidden="true" class="expand-mark">+</span></a><small>${e(t.trainer)}: ${personLink(r, 'trainer')}</small><small class="equipment" title="Hippos">${e(equipmentText(r))}</small></td><td class="form-cell">${recentForm(form[r.horseId])}</td><td>${personLink(r, 'driver')}</td><td class="numeric">${e(r.distance || t.unknown)}</td>${oddsCell(r, toto)}<td><span class="place ${isWinner(r) ? 'first' : ''}">${e(r.absent ? t.absent : resultText(r, 'placing', t.unknown))}</span></td><td class="numeric">${e(kilometerTime(r, t.unknown))}</td><td class="numeric">${hasResult(r) && r.price != null && r.price !== '' ? `${e(r.price)} €` : t.unknown}</td></tr>`).join('')}</tbody></table></div>`;
}

function raceDetail(data, calendarContext = null, order = 'program') {
  const { meeting: m, race: r, races, entries } = data;
  const returnTo = parseRoute(location.hash).params.returnTo;
  const raceLink = item => calendarContext
    ? route('calendar', calendarParams(calendarContext, m, item.number))
    : route('race', { date: m.date, track: m.track, number: item.number, order, ...(returnTo ? { returnTo } : {}) });
  return `${calendarContext ? `<div class="selected-heading"><div><h2>${e(trackName(m))}</h2><p>${e(dateText(m.date, { weekday: 'long' }))} · ${e(m.name || '')}</p></div>${link('race', { date: m.date, track: m.track, number: r.number, order }, icon('external') + `<span class="sr-only">${e(t.fullRace)}</span>`, 'standalone-link')}</div>` : ''}
    ${m.canceled ? badge(t.canceled, 'warning') : ''}<nav class="race-tabs" aria-label="${e(t.raceHeading)}">${races.map(item => `<a href="${e(raceLink(item))}" class="${item.number === r.number ? 'selected' : ''}" ${item.number === r.number ? 'aria-current="page"' : ''}>${e(t.race(item.number))}</a>`).join('')}</nav>
    <section class="race-detail"><div class="race-heading"><div><h2>${e(t.race(r.number))} <span>${e(r.data.plannedTime ? t.at(r.data.plannedTime) : '')}</span></h2><p>${e(raceMeta(r))} · ${e(r.entry_count === null ? t.noUpdate : t.entries(entries.length))}</p></div>${badge(r.has_results ? t.results : r.field_fetched_at ? t.racecard : t.incomplete, r.has_results ? 'success' : '')}</div>
    <div class="table-toolbar"><label>${e(t.sort)}<select id="race-sort"><option value="program" ${order === 'program' ? 'selected' : ''}>${e(t.programOrder)}</option><option value="result" ${order === 'result' ? 'selected' : ''}>${e(t.resultOrder)}</option></select></label></div>
    <div id="race-table">${r.field_fetched_at === null ? empty(t.noField, '') : !entries.length ? empty(t.emptyField, '') : raceTable(entries, order, data.form, data.toto)}</div>
    <div class="table-footer">${note(t.formHint + " " + (r.has_results ? t.resultHint : t.noResultHint) + " " + t.oddsHint)}${totoStatus(data.toto)}${freshness(r.field_fetched_at)}</div></section>`;
}

async function raceView(params) {
  currentRace = await api('race', params);
  const origin = parseRoute(params.returnTo || '');
  const back = ['horse', 'saved', 'person'].includes(origin.name) ? link(origin.name, origin.params, `${icon('back')}${e(origin.name === 'saved' ? t.backSaved : origin.name === 'person' ? t.backPerson : t.backHorse)}`, 'back-link') : '';
  return `${back || link('calendar', { day: params.date, course: params.track, number: params.number, from: params.date, to: params.date, order: raceOrder(params) }, `${icon('back')}${e(t.backCalendar)}`, 'back-link')}${meetingHeader(currentRace.meeting)}${raceDetail(currentRace, null, raceOrder(params))}`;
}

async function horsesView(params) {
  const data = await api('horses', { q: params.q || '', offset: params.offset || '0' });
  return `${header(t.horses)}<form class="horse-search" id="horse-search"><label for="horse-query">${e(t.search)}</label><div class="search-row"><div class="search-input">${icon('search')}<input id="horse-query" name="q" type="search" placeholder="${e(t.searchPlaceholder)}" value="${e(params.q || '')}" maxlength="200"></div><button class="button primary">${e(t.searchButton)}</button></div></form>
    <div class="section-heading"><h2>${e(t.found(data.total))}</h2></div><div class="horse-grid">${data.horses.map(h => link('horse', { id: h.id, returnTo: route('horses', params) }, `<span class="horse-avatar">${icon('horse')}</span><div><h3>${e(h.name)}</h3><p>${e(t.breeds[h.breed] || h.breed || t.unknown)} <span>·</span> ${e(h.country || t.unknown)}</p></div>${icon('arrow')}`, 'horse-card')).join('')}</div>
    ${!data.horses.length ? empty(t.noHorses, t.noHorsesHint) : ''}
    <div class="pagination">${data.offset > 0 ? link('horses', { q: params.q || '', offset: Math.max(0, data.offset - data.limit) }, `${icon('back')}${e(t.previous)}`, 'button') : '<span></span>'}<span>${e(t.page(data.total ? data.offset + 1 : 0, Math.min(data.offset + data.limit, data.total), data.total))}</span>${data.offset + data.limit < data.total ? link('horses', { q: params.q || '', offset: data.offset + data.limit }, `${e(t.next)}${icon('arrow')}`, 'button') : '<span></span>'}</div>`;
}

function personLink(entry, role) {
  const ref = personReference(entry, role);
  const label = entry[`${role}Name`] || (ref ? t.unnamedPerson(ref.id) : t.unknown);
  return ref ? link('person', { ...ref, returnTo: returnContext(location.hash) }, e(label), 'person-link') : e(label);
}

function peoplePagination(name, params, data, label) {
  if (data.total <= data.limit) return '';
  const page = offset => ({...params, offset});
  return `<nav class="pagination" aria-label="${e(label)}">${data.offset ? link(name, page(Math.max(0, data.offset-data.limit)), e(t.previous), 'button') : '<span></span>'}<span>${e(t.page(data.offset+1, Math.min(data.offset+data.limit,data.total),data.total))}</span>${data.offset+data.limit<data.total ? link(name,page(data.offset+data.limit),e(t.next),'button') : '<span></span>'}</nav>`;
}

async function peopleView(params) {
  const role = params.role || 'driver';
  if (['owner','breeder'].includes(role)) return partiesView({...params,role});
  const data = await api('people', {role, q: params.q || '', offset: params.offset || '0'});
  return `${header(t.people)}${peopleTabs(role,params.q || '')}
    <form class="horse-search" id="people-search"><input type="hidden" name="role" value="${e(role)}"><label for="people-query">${e(t.searchPerson)}</label><div class="search-row"><div class="search-input">${icon('search')}<input id="people-query" name="q" type="search" placeholder="${e(t.personPlaceholder)}" value="${e(params.q || '')}" maxlength="200"></div><button class="button primary">${e(t.searchButton)}</button></div></form>
    <div class="section-heading"><h2>${e(t.peopleFound(data.total))}</h2></div>${note(t.peopleScope)}
    ${data.people.length ? `<div class="table-scroll people-directory" tabindex="0" role="region" aria-label="${e(role === 'driver' ? t.drivers : t.trainers)}"><table><thead><tr><th scope="col">${e(t[role])}</th><th scope="col">${e(t.horses)}</th><th scope="col">${e(t.entriesShort)}</th></tr></thead><tbody>${data.people.map(p => `<tr><td>${link('person', {role,id:p.id,returnTo:route('people',{...params,role,offset:data.offset})}, e(p.name || t.unnamedPerson(p.id)), 'horse-name')}<small>${e(t.latestEntry(dateText(p.last_date)))}</small></td><td class="numeric">${e(p.horses)}</td><td class="numeric">${e(p.entries)}</td></tr>`).join('')}</tbody></table></div>` : empty(t.noPeople,t.noPeopleHint)}
    ${peoplePagination('people',{...params,role},data,t.peoplePages)}`;
}

async function personView(params) {
  const data = await api('person', {...params, from:localDay(new Date(overview.now))});
  const {person:p, summary:s} = data;
  const back = personReturnRoute(params.returnTo, p.role);
  const labels = {people:t.backPeople,person:t.backPerson,party:t.backParty,horse:t.backHorse,race:t.backRace,calendar:t.backCalendar,saved:t.backSaved};
  const upcoming = data.period === 'upcoming';
  const otherRole = p.role === 'driver' ? 'trainer' : 'driver';
  const pageParams = {...params,period:data.period};
  return `${link(back.name,back.params,`${icon('back')}${e(labels[back.name])}`,'back-link')}${header(p.name || t.unnamedPerson(p.id),'',e(t[p.role]),freshness(p.fetched_at))}
    <div class="overview-panel horse-stats person-stats">${stats([[s.horses,t.horsesLabel],[s.entries,t.startsLabel],[s.results,t.resultsLabel],[s.wins,t.winsLabel]])}</div>${note(t.personScope)}
    <nav class="segmented people-tabs" aria-label="${e(t.history)}">${['upcoming','history'].map(period => `<a href="${e(route('person',{...params,period,offset:0}))}" ${data.period === period ? 'class="selected" aria-current="page"' : ''}>${e(period === 'upcoming' ? t.upcomingShort : t.historyShort)} (${e(period === 'upcoming' ? s.upcoming : s.entries-s.upcoming)})</a>`).join('')}</nav>
    <div class="section-heading"><h2>${e(upcoming ? t.upcoming : t.history)}</h2></div>${upcoming ? `<p class="section-intro">${e(t.upcomingHint)}</p>` : ''}
    ${peoplePagination('person',pageParams,data,t.startPages)}
    ${data.starts.length ? `<div class="table-scroll person-starts" tabindex="0" role="region" aria-label="${e(t.history)}"><table><thead><tr>${[t.date,t.horse,t.meeting,t.placing,...(upcoming ? [] : [t.kmTime])].map(x => `<th scope="col">${e(x)}</th>`).join('')}</tr></thead><tbody>${data.starts.map(start => `<tr><td>${e(dateText(start.date))}</td><td>${link('horse',{id:start.horse_id,returnTo:route('person',{...pageParams,offset:data.offset})},e(start.data.horseName),'horse-name')}<small>${e(t[otherRole])}: ${personLink(start.data,otherRole)}</small></td><td>${link('race',{date:start.date,track:start.track,number:start.race_number,returnTo:route('person',{...pageParams,offset:data.offset})},`${start.meeting_data.canceled ? `${e(t.canceled)} · ` : ''}${e(start.meeting_data.formattedTrackName || start.city || start.track)}<small>${e(t.race(start.race_number))} · ${e(t.number)} ${e(start.program_number)}${start.data.startType && start.data.startType !== 'TOTO' ? ` · ${e(t.types[start.data.startType] || start.data.startType)}` : ''}</small>`,'horse-name')}</td><td>${e(start.absent ? t.absent : resultText(start.data,'placing',t.unknown))}</td>${upcoming ? '' : `<td>${e(kilometerTime(start.data,t.unknown))}</td>`}</tr>`).join('')}</tbody></table></div>` : empty(upcoming ? t.noUpcoming : t.noHistory,'')}
    ${peoplePagination('person',pageParams,data,t.startPages)}<div class="detail-toolbar">${source()}</div>`;
}

function peopleTabs(role, query = '') {
  const names = {driver:t.drivers,trainer:t.trainers,owner:t.owners,breeder:t.breeders};
  return `<nav class="segmented people-tabs" aria-label="${e(t.people)}">${Object.entries(names).map(([r,name]) => `<a href="${e(route('people',{role:r,q:query}))}" ${role===r ? 'class="selected" aria-current="page"' : ''}>${e(name)}</a>`).join('')}</nav>`;
}

async function partiesView(params) {
  const data = await api('parties',params);
  return `${header(t.people)}${peopleTabs(params.role,params.q || '')}
    <form class="horse-search" id="people-search"><input type="hidden" name="role" value="${e(params.role)}"><label for="people-query">${e(t.partySearch)}</label><div class="search-row"><div class="search-input">${icon('search')}<input id="people-query" name="q" type="search" maxlength="200" value="${e(params.q || '')}" placeholder="${e(t.partyPlaceholder)}"></div><button class="button primary">${e(t.searchButton)}</button></div></form>
    <div class="section-heading"><h2>${e(t.partyFound(data.total))}</h2></div>${note(t.partyScope)}
    ${data.parties.length ? `<div class="table-scroll party-directory" role="region" tabindex="0" aria-label="${e(t[params.role])}"><table><thead><tr><th scope="col">${e(t[params.role])}</th><th scope="col">${e(t.horses)}</th></tr></thead><tbody>${data.parties.map(p => `<tr><td>${link('party',{role:params.role,id:p.id,returnTo:route('people',{...params,offset:data.offset})},e(p.name),'horse-name')}<small>${e(t.updated(timestamp(p.fetched_at)))}</small></td><td class="numeric">${e(p.horses)}</td></tr>`).join('')}</tbody></table></div>` : empty(t.noParties,t.noPartiesHint)}
    ${peoplePagination('people',params,data,t.peoplePages)}`;
}

function relatedHorseCards(horses, returnTo) {
  return `<div class="horse-grid">${horses.map(h => link('horse',{id:h.id,returnTo:returnContext(returnTo)},`<div><h3>${e(h.name)}</h3><p>${e(t.updated(timestamp(h.relationship_fetched_at)))}</p></div>${icon('arrow')}`,'horse-card')).join('')}</div>`;
}

async function partyView(params) {
  const data = await api('party',params);
  const p = data.party;
  const back = personReturnRoute(params.returnTo,p.role);
  const labels = {people:t.backPeople,horse:t.backHorse,party:t.backParty,person:t.backPerson,race:t.backRace,calendar:t.backCalendar,saved:t.backSaved};
  return `${link(back.name,back.params,`${icon('back')}${e(labels[back.name])}`,'back-link')}${header(p.name,'',e(t[p.role]),freshness(p.fetched_at))}${note(t.partyScope + ' ' + t.profileScope)}
    <div class="section-heading"><h2>${e(t.partyHorses)} · ${e(data.total)}</h2></div>
    ${relatedHorseCards(data.horses,route('party',{...params,offset:data.offset}))}${peoplePagination('party',params,data,t.peoplePages)}`;
}

function pedigreeBranches(parents) {
  return `<ul class="pedigree-branches">${['sire','dam'].map(role => {
    const p = parents[role];
    return `<li><span class="pedigree-role">${e(t[role])}</span>${p?.id ? link('horse',{id:p.id,returnTo:returnContext(location.hash)},e(p.name || p.id),'horse-name') : `<span>${e(p?.name || t.unknownParent)}</span>`}${p?.id && !p.fetched_at ? `<small>${e(t.ancestorPending)}</small>` : ''}${p?.cycle ? `<small>${e(t.pedigreeCycle)}</small>` : p && Object.keys(p.parents).length ? pedigreeBranches(p.parents) : ''}</li>`;
  }).join('')}</ul>`;
}

function horseBackground(data) {
  const profile = data.profile;
  const state = data.profile_status;
  const status = state === 'failed' ? t.profileFailed : state === 'pending' ? t.profilePending : t.profileNotCollected;
  if (!profile) return `<section class="horse-background"><div><h2>${e(t.profileTitle)}</h2><p>${e(status)}</p></div></section>`;
  const p = profile.data;
  const party = role => {
    const r = data.parties.find(x=>x.role===role);
    return r ? link('party',{role,id:r.id,returnTo:returnContext(location.hash)},e(r.label),'person-link') : e(t.unknown);
  };
  return `<section class="horse-background"><div class="profile-facts"><h2>${e(t.profileTitle)}</h2><dl><dt>${e(t.owner)}</dt><dd>${party('owner')}</dd><dt>${e(t.breeder)}</dt><dd>${party('breeder')}</dd><dt>${e(t.born)}</dt><dd>${p.birthDate ? e(dateText(p.birthDate)) : e(t.unknown)}${p.birthDate && p.birthDateAccurate === false ? `<small>${e(t.birthApproximate)}</small>` : ''}</dd><dt>${e(t.gender)}</dt><dd>${e(t.genders[p.gender] || p.gender || t.unknown)}${p.dead ? ` · ${e(t.dead)}` : ''}</dd></dl>${freshness(profile.fetched_at)}${['failed','pending'].includes(state) ? `<p>${e(status)}</p>` : ''}</div>
    <div class="pedigree-section"><h2>${e(t.pedigree)}</h2>${pedigreeBranches(data.pedigree)}</div></section>`;
}

function offspringSection(data, params) {
  const page = offset => link('horse',{...params,offspring_offset:offset},e(offset<data.offset ? t.previous : t.next),'button');
  return `<section class="offspring-section"><div class="section-heading"><h2>${e(t.offspring)} · ${e(data.total)}</h2></div>${data.horses.length ? relatedHorseCards(data.horses,route('horse',{...params,offspring_offset:data.offset})) : `<p>${e(t.noOffspring)}</p>`}${data.total>data.limit ? `<nav class="pagination" aria-label="${e(t.offspringPages)}">${data.offset ? page(Math.max(0,data.offset-data.limit)) : '<span></span>'}<span>${e(t.page(data.offset+1,Math.min(data.offset+data.limit,data.total),data.total))}</span>${data.offset+data.limit<data.total ? page(data.offset+data.limit) : '<span></span>'}</nav>` : ''}</section>`;
}

function startsTable(starts, label, upcoming = false) {
  return `<div class="table-scroll history-table${upcoming ? ' upcoming-table' : ''}" tabindex="0" role="region" aria-label="${e(label)}"><table><thead><tr>${[t.date, t.meeting, ...(upcoming ? [] : [t.driver, t.placing, t.kmTime, t.prize])].map(x => `<th scope="col">${e(x)}</th>`).join('')}</tr></thead><tbody>${starts.map(s => `<tr><td class="numeric">${e(dateText(s.date))}</td><td>${link('race', { date: s.date, track: s.track, number: s.race_number, returnTo: returnContext(location.hash) }, `${s.meeting_data.canceled ? `${e(t.canceled)} · ` : ''}${upcoming && s.absent ? `${e(t.absent)} · ` : ''}${e(s.meeting_data.formattedTrackName || s.city || s.track)}<small>${e(t.race(s.race_number))} · ${e(s.data.distance || t.unknown)} m${s.data.startType && s.data.startType !== 'TOTO' ? ` · ${e(t.types[s.data.startType] || s.data.startType)}` : ''}</small>`, 'horse-name')}${upcoming ? `<small>${e(t.driver)}: ${personLink(s.data, 'driver')}</small><small>${e(t.trainer)}: ${personLink(s.data, 'trainer')}</small>` : ''}</td>${upcoming ? '' : `<td>${personLink(s.data, 'driver')}<small>${e(t.trainer)}: ${personLink(s.data, 'trainer')}</small></td><td><span class="place ${isWinner(s.data) ? 'first' : ''}">${e(s.absent ? t.absent : resultText(s.data, 'placing', t.unknown))}</span></td><td class="numeric">${e(kilometerTime(s.data, t.unknown))}</td><td class="numeric">${hasResult(s.data) && s.prize != null && s.prize !== '' ? `${e(s.prize)} €` : t.unknown}</td>`}</tr>`).join('')}</tbody></table></div>`;
}

function savedState() {
  try { return loadSaved(localStorage); }
  catch { return { ids: [], error: true }; }
}

function saveButton(id) {
  const state = savedState();
  return `<button type="button" class="button" data-save="${e(id)}" aria-pressed="${state.ids.includes(id)}">${e(state.ids.includes(id) ? t.removeSaved : t.saveHorse)}</button>`;
}

async function savedView() {
  const state = savedState();
  const intro = header(t.saved) + note(t.savedHint);
  if (state.error) return intro + empty(t.savedError, t.savedErrorHint);
  if (!state.ids.length) return intro + empty(t.noSaved, t.noSavedHint, link('horses', {}, e(t.search), 'button primary'));
  const data = await api('saved', { ids: state.ids.join(','), from: localDay(new Date(overview.now)) });
  return intro + `<div id="save-feedback" role="status"></div><div class="saved-list">${data.horses.map(({ horse: h, starts }) => {
    const { upcoming } = splitStarts(starts, localDay(new Date(overview.now)));
    return `<section class="saved-horse"><div class="section-heading"><h2>${link('horse', { id: h.id, returnTo: route('saved') }, e(h.name))}</h2>${saveButton(h.id)}</div>${upcoming.length ? startsTable(upcoming, t.upcoming, true) : `<p>${e(t.noUpcoming)}</p>`}</section>`;
  }).join('')}${data.missing.map(id => `<section class="saved-horse"><p>${e(t.savedMissing(id))}</p>${saveButton(id)}</section>`).join('')}</div>`;
}

async function horseView(params) {
  const data = await api('horse', params);
  const { horse: h, starts } = data;
  const breed = data.profile?.data.breedFinName || t.breeds[h.breed] || h.breed || t.unknown;
  const { upcoming, history } = splitStarts(starts, localDay(new Date(overview.now)));
  const summary = historyStats(history);
  const back = horseReturnRoute(params.returnTo);
  const backLabel = { horses: t.backHorses, calendar: t.backCalendar, race: t.backRace, saved: t.backSaved, person: t.backPerson, horse:t.backHorse, party:t.backParty }[back.name];
  return `${link(back.name, back.params, `${icon('back')}${e(backLabel)}`, 'back-link')}${header(h.name, '', `${e(breed)} <span>·</span> ${e(h.country || t.unknown)}`, saveButton(h.id))}<div id="save-feedback" role="status"></div>
    <div class="overview-panel horse-stats">${stats([[summary.starts, t.startsLabel], [summary.results, t.resultsLabel], [summary.wins, t.winsLabel]])}</div>${horseBackground(data)}
    <div class="section-heading"><h2>${e(t.upcoming)}</h2></div>${upcoming.length ? `<p class="section-intro">${e(t.upcomingHint)}</p>` : ''}
    ${upcoming.length ? startsTable(upcoming, t.upcoming, true) : `<p class="section-intro">${e(t.noUpcoming)}</p>`}
    <div class="section-heading"><h2>${e(t.history)}</h2></div>
    ${history.length ? startsTable(history, t.history) : `<p>${e(t.noHistory)}</p>`}${offspringSection(data.offspring,params)}
    ${note([t.profileScope, t.pedigreeHint, t.historyHint, t.offspringHint].join(' '))}<div class="detail-toolbar">${freshness(h.fetched_at)}${source()}</div>`;
}

function bind() {
  document.querySelector('#calendar-filter')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    const params = Object.fromEntries(new FormData(form));
    form.elements.to.setCustomValidity(params.to < params.from ? t.invalidRange : '');
    if (form.reportValidity()) location.hash = route('calendar', params);
  });
  document.querySelector('#calendar-filter')?.addEventListener('input', event => event.currentTarget.elements.to.setCustomValidity(''));
  document.querySelector('#calendar-filter select')?.addEventListener('change', event => event.currentTarget.form.requestSubmit());
  document.querySelector('#horse-search')?.addEventListener('submit', event => {
    event.preventDefault();
    location.hash = route('horses', { q: new FormData(event.currentTarget).get('q').trim() });
  });
  document.querySelector('#people-search')?.addEventListener('submit', event => {
    event.preventDefault();
    location.hash = route('people', Object.fromEntries(new FormData(event.currentTarget)));
  });
  document.querySelector('#race-sort')?.addEventListener('change', event => {
    const order = event.target.value;
    const { name, params } = parseRoute(location.hash);
    const selected = name === 'calendar' ? calendarParams(params, currentRace.meeting, currentRace.race.number) : params;
    history.replaceState(null, '', withRaceOrder(route(name, selected), order));
    document.querySelectorAll('.race-tabs a,.quick-races a,.meeting-select,.standalone-link,.calendar-page').forEach(anchor => {
      anchor.href = withRaceOrder(anchor.hash, order);
    });
    if (currentRace.entries.length) document.querySelector('#race-table').innerHTML = raceTable(currentRace.entries, order, currentRace.form, currentRace.toto);
  });
  document.querySelector('#retry')?.addEventListener('click', () => render(true));
}

function previewHistory(starts) {
  return `<table class="preview-table"><thead><tr>${[t.date, t.meeting, t.placing, t.kmTime].map(label => `<th scope="col">${e(label)}</th>`).join('')}</tr></thead><tbody>${starts.slice(0, 5).map(s => `<tr><td>${e(dateText(s.date))}</td><td>${link('race', { date: s.date, track: s.track, number: s.race_number, returnTo: returnContext(location.hash) }, `${e(s.meeting_data.formattedTrackName || s.city || s.track)} · ${e(t.race(s.race_number))}`)}</td><td>${e(s.absent ? t.absent : resultText(s.data, 'placing', t.unknown))}</td><td>${e(kilometerTime(s.data, t.unknown))}</td></tr>`).join('')}</tbody></table>`;
}

async function toggleHorse(linkElement) {
  const row = linkElement.closest('tr');
  if (linkElement.getAttribute('aria-expanded') === 'true') {
    row.nextElementSibling?.remove();
    linkElement.setAttribute('aria-expanded', 'false');
    return;
  }
  linkElement.setAttribute('aria-expanded', 'true');
  const id = linkElement.dataset.preview;
  const preview = document.createElement('tr');
  preview.className = 'horse-preview';
  preview.innerHTML = `<td colspan="9"><div role="status">${e(t.loading)}</div></td>`;
  row.after(preview);
  try {
    const data = await api('horse', { id });
    if (!preview.isConnected) return;
    preview.innerHTML = `<td colspan="9"><div class="preview-heading"><strong>${e(data.horse.name)}</strong><button class="button close-preview" type="button">${e(t.closePreview)}</button></div>${marketHistory(id)}${data.starts.length ? previewHistory(data.starts) : `<p>${e(t.noHistory)}</p>`}<div class="preview-footer">${link('horse', { id, returnTo: returnContext(location.hash) }, `${e(t.fullHorse)} ${icon('arrow')}`, 'text-link')}${freshness(data.horse.fetched_at)}</div></td>`;
  } catch (error) {
    if (error.name !== 'AbortError' && preview.isConnected) {
      preview.innerHTML = `<td colspan="9"><div role="alert">${e(t.error)} <button type="button" class="button close-preview">${e(t.closePreview)}</button></div></td>`;
    }
  }
}

app.addEventListener('click', event => {
  const save = event.target.closest('[data-save]');
  if (save) {
    try {
      const ids = toggleSaved(localStorage, save.dataset.save);
      if (parseRoute(location.hash).name === 'saved') render(true);
      else {
        const active = ids.includes(save.dataset.save);
        save.setAttribute('aria-pressed', String(active));
        save.textContent = active ? t.removeSaved : t.saveHorse;
        document.querySelector('#save-feedback').textContent = active ? t.savedDone : t.savedRemoved;
      }
    } catch (error) {
      document.querySelector('#save-feedback').textContent = error.message === 'limit' ? t.savedLimit : t.savedErrorHint;
    }
  }
  const previewLink = event.target.closest('a[data-preview]');
  if (previewLink && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button === 0) {
    event.preventDefault();
    toggleHorse(previewLink);
  }
  const close = event.target.closest('.close-preview');
  if (close) {
    const preview = close.closest('tr.horse-preview');
    const trigger = preview.previousElementSibling.querySelector('[data-preview]');
    preview.remove();
    trigger.setAttribute('aria-expanded', 'false');
    trigger.focus({ preventScroll: true });
  }
});

async function render(focus = false) {
  controller?.abort();
  controller = new AbortController();
  const turn = ++generation;
  const { name, params } = parseRoute(location.hash);
  const nextRoute = { name, params };
  const inPlace = sameView(renderedRoute, nextRoute);
  if (!document.querySelector('#main')) shell(name);
  const main = document.querySelector('#main');
  const active = document.activeElement;
  const focusKey = { id: active.id, href: active.getAttribute('href'), name: active.getAttribute('name'),
    label: active.textContent,
    region: active.closest('.race-tabs') ? '.race-tabs' : active.closest('.quick-races') ? '.quick-races'
      : active.closest('.pagination') ? '.pagination' : '' };
  const position = { x: window.scrollX, y: window.scrollY };
  const regions = ['.meeting-browser', '.meeting-list', '.race-tabs', '#race-table .table-scroll'];
  const scrolls = regions.map(selector => {
    const el = document.querySelector(selector);
    return { selector, x: el?.scrollLeft || 0, y: el?.scrollTop || 0 };
  });
  // Keep the old content while loading and enough room below the viewport to
  // preserve its position, without retaining a long directory's blank tail.
  if (inPlace) main.style.minHeight = `${Math.max(0, position.y + window.innerHeight - main.offsetTop)}px`;
  document.querySelector('#main').setAttribute('aria-busy', 'true');
  document.querySelector('#race-sort')?.setAttribute('disabled', '');
  try {
    const freshOverview = await api('overview');
    if (turn !== generation) return;
    overview = freshOverview;
    const views = { calendar: calendarView, meeting: meetingView, race: raceView, horses: horsesView, horse: horseView, saved: savedView, coverage: coverageView, people: peopleView, person: personView, party: partyView };
    if (!views[name]) throw Object.assign(new Error('Unknown page'), { status: 404 });
    const content = await views[name](params);
    if (turn !== generation) return;
    renderedRoute = nextRoute;
    main.innerHTML = content;
    main.removeAttribute('aria-busy');
    if (!inPlace) main.style.minHeight = '';
    const section = ['meeting','race'].includes(name) ? 'calendar'
      : name === 'horse' ? 'horses' : ['person','party'].includes(name) ? 'people' : name;
    document.querySelectorAll('.nav-link').forEach(el => {
      const selected = parseRoute(el.hash).name === section;
      el.classList.toggle('active', selected);
      if (selected) el.setAttribute('aria-current','page');
      else el.removeAttribute('aria-current');
    });
    document.title = `${document.querySelector('h1').textContent} · ${t.brand}`;
    bind();
    if (inPlace) {
      for (const {selector,x,y} of scrolls) {
        const el = document.querySelector(selector);
        if (el) { el.scrollLeft = x; el.scrollTop = y; }
      }
      const target = focusKey.id ? document.getElementById(focusKey.id)
        : focusKey.href ? [...main.querySelectorAll(focusKey.region ? `${focusKey.region} a` : 'a')].find(el => el.getAttribute('href') === focusKey.href
          || (focusKey.region === '.pagination' && el.textContent === focusKey.label))
        : focusKey.name ? [...main.querySelectorAll('[name]')].find(el => el.name === focusKey.name) : null;
      if (target) target.focus({preventScroll:true});
      else if (focus) main.focus({preventScroll:true});
      window.scrollTo(position.x, position.y);
    } else if (focus) {
      document.querySelector('h1').focus({preventScroll:true});
      window.scrollTo(0, 0);
    }
  } catch (error) {
    if (turn !== generation || error.name === 'AbortError') return;
    document.querySelector('#main').removeAttribute('aria-busy');
    document.title = `${error.status === 404 ? t.notFound : t.error} · ${t.brand}`;
    document.querySelector('#main').innerHTML = `<div role="alert">${empty(error.status === 404 ? t.notFound : t.error, error.status === 404 ? t.notFoundHint : t.errorHint, `<button class="button primary" id="retry">${e(t.retry)}</button>${link('calendar', {}, e(t.backCalendar), 'button')}`)}</div>`;
    bind();
  }
}
window.addEventListener('hashchange', () => render(true));
document.querySelector('.skip').addEventListener('click', event => {
  event.preventDefault();
  document.querySelector('#main').focus();
});
render();
