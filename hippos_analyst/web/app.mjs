import { loadSaved, toggleSaved } from './saved.mjs';
import { fi as t } from './locales/fi.mjs';
import { escapeHtml as e, localDay, addDays, route, parseRoute, dateRange, orderEntries, historyStats, kilometerTime, splitStarts, isWinner, hasResult, resultText, calendarSelection, calendarParams, calendarPage, raceOrder, withRaceOrder, horseReturnRoute } from './model.mjs';

const app = document.querySelector('#app');
let overview, controller, generation = 0, currentRace, renderedRoute, renderedCalendarPage;
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
  const response = await fetch(`/api/${path}?${new URLSearchParams(params)}`, { signal: controller.signal });
  if (!response.ok) throw Object.assign(new Error('API request failed'), { status: response.status });
  return response.json();
}

function shell(name) {
  const horses = ['horses', 'horse'].includes(name);
  app.innerHTML = `<header class="app-header"><a href="#/calendar" class="brand"><span class="brand-mark">${icon('horse')}</span><span>${e(t.brand)}</span></a>
    <nav aria-label="${e(t.workspace)}">${link('calendar', {}, `${icon('calendar')}<span>${e(t.calendar)}</span>`, ['calendar', 'meeting', 'race'].includes(name) ? 'nav-link active' : 'nav-link')}${link('horses', {}, `${icon('horse')}<span>${e(t.horses)}</span>`, horses ? 'nav-link active' : 'nav-link')}${link('saved', {}, e(t.saved), name === 'saved' ? 'nav-link active' : 'nav-link')}${link('coverage', {}, e(t.coverageTitle), name === 'coverage' ? 'nav-link active' : 'nav-link')}</nav>
    <span class="local-pill"><i></i>${e(t.local)}</span><button id="refresh-view" class="button" type="button">${e(t.refresh)}</button></header>
    <main id="main" tabindex="-1"><div class="loading" role="status">${e(t.loading)}</div></main>
    <footer><span>${e(t.source)} · ${e(t.sourceTime)}</span><span>${e(t.localHint)}</span></footer>`;
}

function header(title, description, eyebrow = '', extra = '') {
  return `<div class="page-heading"><div>${eyebrow ? `<div class="eyebrow">${eyebrow}</div>` : ''}<h1 tabindex="-1">${e(title)}</h1><p>${e(description)}</p></div>${extra}</div>`;
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
  const n = data.days.filter(d => d.fetched_at !== null).length;
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
  return `${header(t.calendar, t.workspaceIntro, '', `<div class="archive-summary"><strong>${e(t.calendarSummary(overview.meeting_count, overview.race_count, overview.horse_count))}</strong>${freshness(overview.last_fetched_at)}</div>`)}
    <form id="calendar-filter" class="filters"><div class="segmented">${link('calendar', { track: params.track || '' }, e(t.near), params.range !== 'all' && !params.from ? 'selected' : '')}${link('calendar', { from: addDays(today, -6), to: today, track: params.track || '' }, e(t.lastWeek))}${link('calendar', { range: 'all', track: params.track || '' }, e(t.archive), params.range === 'all' ? 'selected' : '')}</div>
    <label>${e(t.from)}<input name="from" type="date" value="${e(range.from)}" required></label><label>${e(t.to)}<input name="to" type="date" value="${e(range.to)}" required></label><label class="track-filter">${e(t.track)}<select name="track"><option value="">${e(t.allTracks)}</option>${Object.entries(overview.tracks).map(([code, label]) => `<option value="${e(code)}" ${code === params.track ? 'selected' : ''}>${e(label)}</option>`).join('')}</select></label><button type="submit" class="button primary">${e(t.apply)}</button></form>
    <div class="coverage"><span class="coverage-dot"></span>${link('coverage', {}, e(n ? t.coveredDays(n) : t.noDays))}${overview.pending ? `<span class="queue">${e(t.queue(overview.pending))}</span>` : ''}${overview.paused ? badge(t.paused, 'warning') : overview.failed ? badge(t.failed, 'warning') : ''}</div>
    <div class="calendar-workspace"><section class="meeting-browser" aria-label="${e(t.selectMeeting)}"><div class="meeting-browser-heading"><h2>${e(t.meetingHeading)}</h2><div>${link('calendar', changeWeek(-7), icon('back') + `<span class="sr-only">${e(t.earlier)}</span>`, 'week-arrow')}${link('calendar', changeWeek(7), icon('arrow') + `<span class="sr-only">${e(t.later)}</span>`, 'week-arrow')}</div></div>
    ${pages}<div class="meeting-list">${data.meetings.map(m => {
      const selected = selection.meeting.date === m.date && selection.meeting.track === m.track;
      const label = m.canceled ? t.canceled : m.data.hasPublishedResults ? t.results : t.racecard;
      return `<article class="meeting-card${selected ? ' selected' : ''}"><a class="meeting-select" href="${e(route('calendar', calendarParams(params, m, m.races[0]?.number)))}" ${selected ? 'aria-current="true"' : ''}><div class="meeting-meta"><strong>${e(dateText(m.date, { weekday: 'short', year: undefined }))}</strong><span>${e(m.start_time ? t.at(m.start_time.slice(0, 5)) : t.unknown)}</span></div><h3>${e(trackName(m))}</h3><p class="meeting-name">${e(m.name || t.unknown)}</p><div class="meeting-bottom">${badge(label, m.canceled ? 'warning' : m.data.hasPublishedResults ? 'success' : '')}${m.date === today ? badge(t.today, 'accent') : m.date === addDays(today, 1) ? badge(t.tomorrow, 'accent') : ''}<span>${e(t.fields(m.collected_races, m.race_count))}</span></div></a>
      <div class="quick-races" aria-label="${e(t.raceHeading)}">${m.races.map(r => `<a href="${e(route('calendar', calendarParams(params, m, r.number)))}" aria-label="${e(t.directRace(r.number))}" ${selected && selection.number === r.number ? 'aria-current="true"' : ''}>${e(r.number)}</a>`).join('')}</div></article>`;
    }).join('')}</div><p class="footnote">${e(t.coverageHint)}</p></section><section class="selected-race" id="selected-race" aria-label="${e(t.selectedMeeting)}" tabindex="-1">${data.meetings.length ? detail : empty(t.empty, t.emptyHint, link('calendar', { range: 'all', track: params.track || '' }, e(t.archive), 'button'))}</section></div>`;
}

async function coverageView(params) {
  const data = await api('coverage', { offset: params.offset || '0' });
  const status = day => day.fetched_at === null ? t.notCollected : day.meetings === 0 ? t.emptyCalendar : day.missing_lists || day.fields < day.races ? t.partialCollection : t.completeCollection;
  return `${header(t.coverageTitle, t.coverageIntro, '', freshness(overview.last_fetched_at))}
    <div class="collection-status" role="status">${e(overview.paused ? t.pausedHint : overview.failed ? t.failedHint : t.collectionHint)} ${e(t.queue(overview.pending))}</div>
    <p class="section-intro">${e(t.coverageMeaning)}</p>
    ${data.days.length ? `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.coverageTitle)}"><table><thead><tr>${[t.date, t.collectionState, t.meetingHeading, t.racecard, t.calendarUpdated].map(x => `<th scope="col">${e(x)}</th>`).join('')}</tr></thead><tbody>${data.days.map(day => `<tr><td>${link('calendar', {from:day.date,to:day.date}, e(dateText(day.date)))}</td><td>${e(status(day))}${day.status === 'failed' ? `<small>${e(t.failed)}</small>` : day.status === 'pending' && day.fetched_at !== null ? `<small>${e(t.refreshPending)}</small>` : ''}</td><td class="numeric">${day.fetched_at === null ? t.unknown : e(day.meetings)}</td><td>${day.fetched_at === null ? t.unknown : e(t.fields(day.fields, day.races))}${day.missing_lists ? `<small>${e(t.missingLists(day.missing_lists))}</small>` : ''}</td><td>${e(timestamp(day.fetched_at))}</td></tr>`).join('')}</tbody></table></div>` : empty(t.noCoverage, t.noCoverageHint)}
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
    <div class="section-heading"><h2>${e(t.raceHeading)}</h2></div><p class="section-intro">${e(t.raceIntro)}</p>
    <div class="race-grid">${races.map(r => link('race', { date: m.date, track: m.track, number: r.number }, `<div class="race-tile-top"><span class="race-number">${e(r.number)}</span>${badge(r.has_results ? t.results : r.field_fetched_at ? t.racecard : t.incomplete, r.has_results ? 'success' : '')}</div><h3>${e(t.race(r.number))}</h3><p>${e(raceMeta(r))}</p><div class="race-tile-bottom"><span>${r.data.plannedTime ? `${e(t.at(r.data.plannedTime))} · ` : ''}${e(r.entry_count !== null ? t.entries(r.entry_count) : t.noUpdate)}</span>${icon('arrow')}</div>`, 'race-tile')).join('')}</div>
    ${!races.length ? empty(t.noRaces, t.noRacesHint) : ''}`;
}

function recentForm(starts = []) {
  if (!starts.length) return `<span class="muted">${e(t.noPriorForm)}</span>`;
  return `<ol class="runner-form">${starts.map(s => `<li><strong class="${isWinner(s.data) ? 'form-win' : ''}">${e(s.absent ? t.absent : resultText(s.data, 'placing', t.unknown))}</strong><span title="${e(dateText(s.date))}">${e(dateText(s.date, {year: s.date.slice(0,4) === currentRace.meeting.date.slice(0,4) ? undefined : '2-digit'}))}</span>${s.data.startType && s.data.startType !== 'TOTO' ? `<small>${e(t.types[s.data.startType] || s.data.startType)}</small>` : ''}</li>`).join('')}</ol>`;
}

function raceTable(entries, order = 'program', form = {}) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.racecard)}"><table><thead><tr>${[t.number, t.horse, t.priorForm, t.driver, t.distance, t.placing, t.kmTime, t.prize].map(label => `<th scope="col">${e(label)}</th>`).join('')}</tr></thead><tbody>${orderEntries(entries, order).map(r => `<tr class="${r.absent ? 'scratched' : isWinner(r) ? 'winner' : ''}"><td><span class="program-number">${e(r.programNumber)}</span></td><td><a href="${e(route('horse', { id: r.horseId, returnTo: location.hash }))}" class="horse-name" data-preview="${e(r.horseId)}" aria-expanded="false" title="${e(t.expandHorse)}">${e(r.horseName)}<span aria-hidden="true" class="expand-mark">+</span></a><small>${e(t.trainer)}: ${e(r.trainerName || t.unknown)}</small></td><td class="form-cell">${recentForm(form[r.horseId])}</td><td>${e(r.driverName || t.unknown)}</td><td class="numeric">${e(r.distance || t.unknown)}</td><td><span class="place ${isWinner(r) ? 'first' : ''}">${e(r.absent ? t.absent : resultText(r, 'placing', t.unknown))}</span></td><td class="numeric">${e(kilometerTime(r, t.unknown))}</td><td class="numeric">${hasResult(r) && r.price != null && r.price !== '' ? `${e(r.price)} €` : t.unknown}</td></tr>`).join('')}</tbody></table></div>`;
}

function raceDetail(data, calendarContext = null, order = 'program') {
  const { meeting: m, race: r, races, entries } = data;
  const returnTo = parseRoute(location.hash).params.returnTo;
  const raceLink = item => calendarContext
    ? route('calendar', calendarParams(calendarContext, m, item.number))
    : route('race', { date: m.date, track: m.track, number: item.number, order, ...(returnTo ? { returnTo } : {}) });
  return `${calendarContext ? `<div class="selected-heading"><div><h2>${e(trackName(m))}</h2><p>${e(dateText(m.date, { weekday: 'long' }))} · ${e(m.name || '')}</p></div>${link('race', { date: m.date, track: m.track, number: r.number, order }, icon('external') + `<span class="sr-only">${e(t.fullRace)}</span>`, 'standalone-link')}</div>` : ''}
    ${m.canceled ? badge(t.canceled, 'warning') : ''}<nav class="race-tabs" aria-label="${e(t.raceHeading)}">${races.map(item => `<a href="${e(raceLink(item))}" class="${item.number === r.number ? 'selected' : ''}" ${item.number === r.number ? 'aria-current="page"' : ''}>${e(t.race(item.number))}</a>`).join('')}</nav>
    <section class="race-detail"><div class="race-heading"><div><h2>${e(t.race(r.number))} <span>${e(r.data.plannedTime ? t.at(r.data.plannedTime) : '')}</span></h2><p>${e(raceMeta(r))}</p></div>${badge(r.has_results ? t.results : r.field_fetched_at ? t.racecard : t.incomplete, r.has_results ? 'success' : '')}</div>
    <div class="table-toolbar"><span>${e(r.entry_count === null ? t.noUpdate : t.entries(entries.length))}</span><small>${e(t.raceTip)}</small><label>${e(t.sort)}<select id="race-sort"><option value="program" ${order === 'program' ? 'selected' : ''}>${e(t.programOrder)}</option><option value="result" ${order === 'result' ? 'selected' : ''}>${e(t.resultOrder)}</option></select></label></div>
    <p class="form-note">${e(t.formHint)}</p>
    <div id="race-table">${r.field_fetched_at === null ? empty(t.noField, '') : !entries.length ? empty(t.emptyField, '') : raceTable(entries, order, data.form)}</div>
    <div class="table-footer"><span>${e(r.has_results ? t.resultHint : t.noResultHint)}</span>${freshness(r.field_fetched_at)}</div></section>`;
}

async function raceView(params) {
  currentRace = await api('race', params);
  const origin = parseRoute(params.returnTo || '');
  const back = ['horse', 'saved'].includes(origin.name) ? link(origin.name, origin.params, `${icon('back')}${e(origin.name === 'saved' ? t.backSaved : t.backHorse)}`, 'back-link') : '';
  return `${back || link('calendar', { day: params.date, course: params.track, number: params.number, from: params.date, to: params.date, order: raceOrder(params) }, `${icon('back')}${e(t.backCalendar)}`, 'back-link')}${meetingHeader(currentRace.meeting)}${raceDetail(currentRace, null, raceOrder(params))}`;
}

async function horsesView(params) {
  const data = await api('horses', { q: params.q || '', offset: params.offset || '0' });
  return `${header(t.horses, t.horsesIntro)}<form class="horse-search" id="horse-search"><label for="horse-query">${e(t.search)}</label><div class="search-row"><div class="search-input">${icon('search')}<input id="horse-query" name="q" type="search" placeholder="${e(t.searchPlaceholder)}" value="${e(params.q || '')}" maxlength="200"></div><button class="button primary">${e(t.searchButton)}</button></div></form>
    <div class="section-heading"><h2>${e(t.found(data.total))}</h2></div><div class="horse-grid">${data.horses.map(h => link('horse', { id: h.id, returnTo: route('horses', params) }, `<span class="horse-avatar">${icon('horse')}</span><div><h3>${e(h.name)}</h3><p>${e(t.breeds[h.breed] || h.breed || t.unknown)} <span>·</span> ${e(h.country || t.unknown)}</p></div>${icon('arrow')}`, 'horse-card')).join('')}</div>
    ${!data.horses.length ? empty(t.noHorses, t.noHorsesHint) : ''}
    <div class="pagination">${data.offset > 0 ? link('horses', { q: params.q || '', offset: Math.max(0, data.offset - data.limit) }, `${icon('back')}${e(t.previous)}`, 'button') : '<span></span>'}<span>${e(t.page(data.total ? data.offset + 1 : 0, Math.min(data.offset + data.limit, data.total), data.total))}</span>${data.offset + data.limit < data.total ? link('horses', { q: params.q || '', offset: data.offset + data.limit }, `${e(t.next)}${icon('arrow')}`, 'button') : '<span></span>'}</div>`;
}

function startsTable(starts, label, upcoming = false) {
  return `<div class="table-scroll history-table${upcoming ? ' upcoming-table' : ''}" tabindex="0" role="region" aria-label="${e(label)}"><table><thead><tr>${[t.date, t.meeting, ...(upcoming ? [] : [t.driver, t.placing, t.kmTime, t.prize])].map(x => `<th scope="col">${e(x)}</th>`).join('')}</tr></thead><tbody>${starts.map(s => `<tr><td class="numeric">${e(dateText(s.date))}</td><td>${link('race', { date: s.date, track: s.track, number: s.race_number, returnTo: location.hash }, `${s.meeting_data.canceled ? `${e(t.canceled)} · ` : ''}${upcoming && s.absent ? `${e(t.absent)} · ` : ''}${e(s.meeting_data.formattedTrackName || s.city || s.track)}<small>${e(t.race(s.race_number))} · ${e(s.data.distance || t.unknown)} m${s.data.startType && s.data.startType !== 'TOTO' ? ` · ${e(t.types[s.data.startType] || s.data.startType)}` : ''}</small>`, 'horse-name')}${upcoming ? `<small>${e(t.driver)}: ${e(s.data.driverName || t.unknown)}</small>` : ''}</td>${upcoming ? '' : `<td>${e(s.data.driverName || t.unknown)}</td><td><span class="place ${isWinner(s.data) ? 'first' : ''}">${e(s.absent ? t.absent : resultText(s.data, 'placing', t.unknown))}</span></td><td class="numeric">${e(kilometerTime(s.data, t.unknown))}</td><td class="numeric">${hasResult(s.data) && s.prize != null && s.prize !== '' ? `${e(s.prize)} €` : t.unknown}</td>`}</tr>`).join('')}</tbody></table></div>`;
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
  const intro = header(t.saved, t.savedHint);
  if (state.error) return intro + empty(t.savedError, t.savedErrorHint);
  if (!state.ids.length) return intro + empty(t.noSaved, t.noSavedHint, link('horses', {}, e(t.search), 'button primary'));
  const data = await api('saved', { ids: state.ids.join(','), from: localDay(new Date(overview.now)) });
  return intro + `<div id="save-feedback" role="status"></div><div class="saved-list">${data.horses.map(({ horse: h, starts }) => {
    const { upcoming } = splitStarts(starts, localDay(new Date(overview.now)));
    return `<section class="saved-horse"><div class="section-heading"><h2>${link('horse', { id: h.id, returnTo: route('saved') }, e(h.name))}</h2>${saveButton(h.id)}</div>${upcoming.length ? startsTable(upcoming, t.upcoming, true) : `<p>${e(t.noUpcoming)}</p>`}</section>`;
  }).join('')}${data.missing.map(id => `<section class="saved-horse"><p>${e(t.savedMissing(id))}</p>${saveButton(id)}</section>`).join('')}</div>`;
}

async function horseView(params) {
  const { horse: h, starts } = await api('horse', params);
  const { upcoming, history } = splitStarts(starts, localDay(new Date(overview.now)));
  const summary = historyStats(history);
  const back = horseReturnRoute(params.returnTo);
  const backLabel = { horses: t.backHorses, calendar: t.backCalendar, race: t.backRace, saved: t.backSaved }[back.name];
  return `${link(back.name, back.params, `${icon('back')}${e(backLabel)}`, 'back-link')}${header(h.name, t.horseIntro, `${e(t.breeds[h.breed] || h.breed || t.unknown)} <span>·</span> ${e(h.country || t.unknown)}`, saveButton(h.id))}<div id="save-feedback" role="status"></div>
    <div class="overview-panel horse-stats">${stats([[summary.starts, t.startsLabel], [summary.results, t.resultsLabel], [summary.wins, t.winsLabel]])}</div>
    <div class="section-heading"><h2>${e(t.upcoming)}</h2></div><p class="section-intro">${e(t.upcomingHint)}</p>
    ${upcoming.length ? startsTable(upcoming, t.upcoming, true) : `<p class="section-intro">${e(t.noUpcoming)}</p>`}
    <div class="section-heading"><h2>${e(t.history)}</h2></div><p class="section-intro">${e(t.historyHint)}</p>
    ${history.length ? startsTable(history, t.history) : empty(t.noHistory, '')}
    <div class="detail-toolbar"><small>${e(t.horseId)}: ${e(h.id)}</small>${freshness(h.fetched_at)}${source()}</div>`;
}

function bind() {
  document.querySelector('#refresh-view').onclick = () => render(false);
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
  document.querySelector('#race-sort')?.addEventListener('change', event => {
    const order = event.target.value;
    const { name, params } = parseRoute(location.hash);
    const selected = name === 'calendar' ? calendarParams(params, currentRace.meeting, currentRace.race.number) : params;
    history.replaceState(null, '', withRaceOrder(route(name, selected), order));
    document.querySelectorAll('.race-tabs a,.quick-races a,.meeting-select,.standalone-link,.calendar-page').forEach(anchor => {
      anchor.href = withRaceOrder(anchor.hash, order);
    });
    if (currentRace.entries.length) document.querySelector('#race-table').innerHTML = raceTable(currentRace.entries, order, currentRace.form);
  });
  document.querySelector('#retry')?.addEventListener('click', () => render(true));
}

function previewHistory(starts) {
  return `<table class="preview-table"><thead><tr>${[t.date, t.meeting, t.placing, t.kmTime].map(label => `<th scope="col">${e(label)}</th>`).join('')}</tr></thead><tbody>${starts.slice(0, 5).map(s => `<tr><td>${e(dateText(s.date))}</td><td>${link('race', { date: s.date, track: s.track, number: s.race_number, returnTo: location.hash }, `${e(s.meeting_data.formattedTrackName || s.city || s.track)} · ${e(t.race(s.race_number))}`)}</td><td>${e(s.absent ? t.absent : resultText(s.data, 'placing', t.unknown))}</td><td>${e(kilometerTime(s.data, t.unknown))}</td></tr>`).join('')}</tbody></table>`;
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
  preview.innerHTML = `<td colspan="8"><div role="status">${e(t.loading)}</div></td>`;
  row.after(preview);
  try {
    const data = await api('horse', { id });
    if (!preview.isConnected) return;
    preview.innerHTML = `<td colspan="8"><div class="preview-heading"><strong>${e(data.horse.name)}</strong><button class="button close-preview" type="button">${e(t.closePreview)}</button></div><p>${e(t.previewHint)}</p>${data.starts.length ? previewHistory(data.starts) : `<p>${e(t.noHistory)}</p>`}<div class="preview-footer">${link('horse', { id, returnTo: location.hash }, `${e(t.fullHorse)} ${icon('arrow')}`, 'text-link')}${freshness(data.horse.fetched_at)}</div></td>`;
  } catch (error) {
    if (error.name !== 'AbortError' && preview.isConnected) {
      preview.innerHTML = `<td colspan="8"><div role="alert">${e(t.error)} <button type="button" class="button close-preview">${e(t.closePreview)}</button></div></td>`;
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
    trigger.focus();
  }
});

async function render(focus = false) {
  controller?.abort();
  controller = new AbortController();
  const turn = ++generation;
  const { name, params } = parseRoute(location.hash);
  const sameCalendar = name === 'calendar' && renderedRoute === 'calendar';
  const pageKey = JSON.stringify([params.from, params.to, params.range, params.track, params.offset]);
  const samePage = sameCalendar && renderedCalendarPage === pageKey;
  const previousScroll = samePage ? document.querySelector('.meeting-browser')?.scrollTop || 0 : 0;
  const previousHorizontal = samePage ? document.querySelector('.meeting-list')?.scrollLeft || 0 : 0;
  if (!sameCalendar) shell(name);
  document.querySelector('#main').setAttribute('aria-busy', 'true');
  document.querySelector('#race-sort')?.setAttribute('disabled', '');
  try {
    const freshOverview = await api('overview');
    if (turn !== generation) return;
    overview = freshOverview;
    const views = { calendar: calendarView, meeting: meetingView, race: raceView, horses: horsesView, horse: horseView, saved: savedView, coverage: coverageView };
    if (!views[name]) throw Object.assign(new Error('Unknown page'), { status: 404 });
    const content = await views[name](params);
    if (turn !== generation) return;
    renderedRoute = name;
    renderedCalendarPage = pageKey;
    const restoreTrack = sameCalendar && document.activeElement.matches('#calendar-filter select');
    document.querySelector('#main').innerHTML = content;
    document.querySelector('#main').removeAttribute('aria-busy');
    if (sameCalendar) {
      const browser = document.querySelector('.meeting-browser');
      if (browser) browser.scrollTop = previousScroll;
      const list = document.querySelector('.meeting-list');
      if (list) list.scrollLeft = previousHorizontal;
    }
    document.title = `${document.querySelector('h1').textContent} · ${t.brand}`;
    document.querySelectorAll('.nav-link.active,.race-tabs .selected').forEach(el => el.setAttribute('aria-current', 'page'));
    bind();
    if (restoreTrack) {
      document.querySelector('#calendar-filter select').focus({ preventScroll: true });
    } else if (focus) {
      const selected = sameCalendar && params.day && document.querySelector('#selected-race');
      (selected || document.querySelector('h1')).focus({ preventScroll: true });
      if (!sameCalendar) window.scrollTo(0, 0);
      else if (selected && matchMedia('(max-width: 1000px)').matches) selected.scrollIntoView({ block: 'start' });
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
