import { loadSaved, toggleSaved } from './saved.mjs';
import { trackMap } from './track-map.mjs';
import { photoFigure, handlePhotoError } from './photos.mjs';
import { fi as t } from './locales/fi.mjs';
import { escapeHtml as e, localDay, addDays, route, parseRoute, dateRange, orderEntries, coverageState, kilometerTime, splitStarts, isWinner, hasResult, resultText, calendarSelection, calendarParams, calendarPage, raceOrder, horseReturnRoute, personReturnRoute, personReference, returnContext, sameView, runnerMarket, equipmentCodes, nextSort, calendarRaceRoute } from './model.mjs';

const app = document.querySelector('#app');
app.addEventListener('error', handlePhotoError, true);
let overview, controller, generation = 0, currentRace, renderedRoute, searchTimer;
const previewCache = new Map();
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
const link = (name, params, label, cls = '') => `<a class="${cls}" ${cls.split(' ').includes('selected')?'aria-current="page"':''} href="${e(name === 'race' ? calendarRaceRoute(params) : route(name, params))}">${label}</a>`;
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
    <nav aria-label="${e(t.workspace)}">${link('calendar', {}, `${icon('calendar')}<span>${e(t.calendar)}</span>`, ['calendar', 'meeting', 'race'].includes(name) ? 'nav-link active' : 'nav-link')}${link('horses', {}, `${icon('horse')}<span>${e(t.horses)}</span>`, horses ? 'nav-link active' : 'nav-link')}${link('people', {}, e(t.people), ['people', 'person', 'party'].includes(name) ? 'nav-link active' : 'nav-link')}${link('tracks', {}, `${icon('pin')}<span>${e(t.tracks)}</span>`, ['tracks','track'].includes(name) ? 'nav-link active' : 'nav-link')}${link('saved', {}, e(t.saved), name === 'saved' ? 'nav-link active' : 'nav-link')}${link('coverage', {}, e(t.coverageTitle), name === 'coverage' ? 'nav-link active' : 'nav-link')}</nav>
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
  const sorting = params.sort ? {sort:params.sort,dir:params.dir||'asc'} : {order:raceOrder(params)};
  const changeWeek = delta => ({ ...sorting, from: addDays(range.from, delta), to: addDays(range.to, delta), track: params.track || '' });
  return `${originBack(params.returnTo)}<h1 class="sr-only" tabindex="-1">${e(t.calendar)}</h1>
<div class="calendar-workspace"><section class="meeting-browser" aria-label="${e(t.selectMeeting)}"><div class="meeting-controls"><div class="meeting-browser-heading"><h2>${e(t.meetingHeading)}</h2><div>${link('calendar', changeWeek(-7), icon('back') + `<span class="sr-only">${e(t.earlier)}</span>`, 'week-arrow')}${link('calendar', changeWeek(7), icon('arrow') + `<span class="sr-only">${e(t.later)}</span>`, 'week-arrow')}</div></div>

    <form id="calendar-filter" class="filters sidebar-filters"><div class="segmented">${link('calendar', { ...sorting, track: params.track || '' }, e(t.near), params.range !== 'all' && !params.from ? 'selected' : '')}${link('calendar', { ...sorting, from: addDays(today, -6), to: today, track: params.track || '' }, e(t.lastWeek))}${link('calendar', { ...sorting, range: 'all', track: params.track || '' }, e(t.archive), params.range === 'all' ? 'selected' : '')}</div>
    <details class="custom-dates"><summary>${e(dateText(range.from,{year:undefined}))}–${e(dateText(range.to,{year:undefined}))} · ${e(t.customDates)}</summary><div class="date-fields"><label>${e(t.from)}<input name="from" type="date" value="${e(range.from)}" required></label><label>${e(t.to)}<input name="to" type="date" value="${e(range.to)}" required></label></div></details><label class="track-filter">${e(t.track)}<select name="track"><option value="">${e(t.allTracks)}</option>${Object.entries(overview.tracks).map(([code, label]) => `<option value="${e(code)}" ${code === params.track ? 'selected' : ''}>${e(label)}</option>`).join('')}</select></label><button type="submit" class="button primary">${e(t.apply)}</button></form></div>
    ${pages}<div class="meeting-list">${data.meetings.map(m => {
      const selected = selection.meeting.date === m.date && selection.meeting.track === m.track;
      const label = m.canceled ? t.canceled : m.data.hasPublishedResults ? t.results : t.racecard;
      return `<article class="meeting-card${selected ? ' selected' : ''}"><a class="meeting-select" href="${e(route('calendar', calendarParams(params, m, m.races[0]?.number)))}" ${selected ? 'aria-current="true"' : ''}><div class="meeting-meta"><strong>${e(dateText(m.date, { weekday: 'short', year: undefined }))}</strong><span>${e(m.start_time ? t.at(m.start_time.slice(0, 5)) : t.unknown)}</span></div><h3>${e(trackName(m))}</h3><p class="meeting-name">${e(m.name || t.unknown)}</p><div class="meeting-bottom">${m.canceled || m.data.hasPublishedResults ? badge(label, m.canceled ? 'warning' : 'success') : ''}${m.date === today ? badge(t.today, 'accent') : m.date === addDays(today, 1) ? badge(t.tomorrow, 'accent') : ''}<span>${e(t.fields(m.collected_races, m.race_count))}</span></div></a>
      <div class="quick-races" aria-label="${e(t.raceHeading)}">${m.races.map(r => `<a href="${e(route('calendar', calendarParams(params, m, r.number)))}" aria-label="${e(t.directRace(r.number))}" ${selected && selection.number === r.number ? 'aria-current="true"' : ''}>${e(r.number)}</a>`).join('')}</div></article>`;
    }).join('')}</div></section><section class="selected-race" id="selected-race" aria-label="${e(t.selectedMeeting)}" tabindex="-1">${data.meetings.length ? detail : empty(t.empty, t.emptyHint, link('calendar', { ...sorting, range: 'all', track: params.track || '' }, e(t.archive), 'button'))}</section></div>`;
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
  return header(trackName(m), m.name || '', `${e(dateText(m.date, { weekday: 'long' }))} <span>·</span> ${e(m.start_time ? t.at(m.start_time.slice(0, 5)) : t.unknown)}`, venueLink(m));
}

function venueLink(meeting) {
  return link('track', {id: meeting.track_id, returnTo: returnContext(location.hash)}, `${icon('pin')}${e(t.trackProfile)}`, 'button');
}

const externalLink = (url, label) => `<a href="${e(url)}" target="_blank" rel="noreferrer">${e(label)} ${icon('external')}</a>`;

function trackPhoto(track, compact = false) {
  const image = track.image;
  if (!image) return compact ? `<figure class="track-photo track-photo-missing"><div class="track-photo-placeholder" aria-hidden="true">${icon('pin')}</div><figcaption>${e(t.noTrackPhoto)}</figcaption></figure>` : `<div class="track-no-photo">${icon('pin')}<p>${e(t.noTrackPhoto)}</p></div>`;
  const credit = image.author ? [image.author,image.year].filter(Boolean).join(' · ') : t.trackImageSource(image.publisher);
  const license = image.license_url ? ` · ${externalLink(image.license_url,image.license)}` : '';
  const modification = compact ? t.trackImageCropped : image.rights_status === 'not-specified' ? t.trackImageUnchanged : t.imageResized;
  return `<figure class="track-photo"><img src="${e(image.path)}" width="${image.width}" height="${image.height}" alt="${e(t.trackPhotoAlt(track.name))}" ${compact ? 'loading="lazy"' : ''}><figcaption>${externalLink(image.source, credit)}${license}<span>${e(modification)}</span></figcaption></figure>`;
}

async function tracksView(params) {
  params = params.offset ? {offset:params.offset} : {};
  const data = await api('tracks', {...params, today: localDay(new Date(overview.now))});
  const returnTo = route('tracks', params);
  return `<div class="tracks-workspace">${trackMap(data.rows, returnTo)}<section class="track-results" aria-label="${e(t.tracks)}">${data.rows.length ? `<div class="track-directory">${data.rows.map(track => `<article class="track-card">${trackPhoto(track, true)}<div class="track-card-body"><div class="eyebrow">${icon('pin')} ${e(track.city || t.unknown)} <span>· ${e(track.code)}</span></div><h2>${link('track', {id: track.id, returnTo}, e(track.name))}</h2><p>${e(track.address || t.noTrackAddress)}</p><div class="track-card-meta"><span>${e(t.trackMeetingCount(track.meeting_count))}</span>${track.next_date ? `<span>${e(t.nextTrackMeeting(dateText(track.next_date)))}</span>` : ''}</div></div></article>`).join('')}</div>` : empty(t.noMatches, t.noMatchesHint)}
    ${peoplePagination('tracks', params, data, t.trackPages)}</section></div>${note(t.trackScope)}`;
}

async function trackView(params) {
  const data = await api('track', {...params, today: localDay(new Date(overview.now))});
  const track = data.track, coords = track.coordinates;
  const facts = [[t.trackLocation, track.city], [t.trackAddress, track.address], [t.trackCode, track.code],
    [t.trackCategory, t.trackCategories[track.category] || track.category]];
  if (track.racing_city && track.racing_city !== track.city) facts.push([t.racingCity, track.racing_city]);
  const technical = track.technical;
  const tabs = ['upcoming', 'history'].map(period => link('track', {...params, period, offset: 0},
    e(`${period === 'upcoming' ? t.upcomingShort : t.historyShort} (${data[`${period}_count`]})`), data.period === period ? 'selected' : '')).join('');
  return `${originBack(params.returnTo || route('tracks'))}${header(track.name, track.description || '', `${e(track.city || '')} · ${e(track.code)}`)}
    <div class="track-profile"><section class="track-facts"><h2>${e(t.trackFacts)}</h2><dl>${facts.map(([label,value]) => `<dt>${e(label)}</dt><dd>${e(value || t.unknown)}</dd>`).join('')}</dl>
      <div class="track-links">${track.website ? externalLink(track.website, t.trackWebsite) : ''}${coords ? externalLink(`https://www.openstreetmap.org/?mlat=${coords.latitude}&mlon=${coords.longitude}#map=15/${coords.latitude}/${coords.longitude}`, t.trackMap) : ''}</div>
      ${technical ? `<h3>${e(t.trackTechnical)}</h3><dl>${Object.keys(t.trackDimensions).filter(key => technical[key] != null).map(key => `<dt>${e(t.trackDimensions[key])}</dt><dd>${e(technical[key])} m</dd>`).join('')}</dl>` : `<p class="muted">${e(t.noTrackTechnical)}</p>`}
    </section>${trackPhoto(track)}</div>
    <section class="track-meetings"><div class="section-heading"><h2>${e(t.trackMeetings)}</h2><span>${e(t.trackMeetingCount(data.meeting_count))}</span></div>
      <nav class="profile-tabs" aria-label="${e(t.trackMeetings)}">${tabs}</nav>
      ${data.rows.length ? `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.trackMeetings)}"><table><thead><tr>${[t.date,t.meetingHeading,t.raceHeading,t.collectionState].map(label => `<th scope="col">${e(label)}</th>`).join('')}</tr></thead><tbody>${data.rows.map(m => `<tr><td>${link('calendar', {from:m.date,to:m.date,track:m.track,day:m.date,course:m.track,returnTo:returnContext(location.hash)}, e(dateText(m.date)), 'horse-name')}<small>${e(m.start_time || '')}</small></td><td>${e(m.name || track.name)}${m.canceled ? badge(t.canceled,'warning') : ''}</td><td><div class="track-races">${m.races.map(r => link('race', {date:m.date,track:m.track,number:r.number,returnTo:returnContext(location.hash)}, e(t.race(r.number)), 'text-link')).join('')}</div></td><td>${e(t.fields(m.collected_races,m.race_count))}${!m.races_fetched_at ? `<small>${e(t.noRacesHint)}</small>` : ''}</td></tr>`).join('')}</tbody></table></div>` : empty(t.noTrackMeetings, t.trackScope)}
      ${peoplePagination('track', {...params,period:data.period}, data, t.meetingPages)}
    </section>
    <section class="track-sources"><h2>${e(t.trackSources)}</h2><ul>${track.sources.map(s => `<li>${externalLink(s.url, s.kind === 'technical' ? t.trackTechnical : t.trackDirectorySource)} · ${e(t.sourceChecked(dateText(s.checked)))}</li>`).join('')}${track.fetched_at ? `<li>${source()} · ${e(t.trackObserved(timestamp(track.fetched_at)))}${track.observed.date ? ` · ${e(t.trackObservationDay(dateText(track.observed.date)))}` : ''}</li>` : ''}</ul>${note(t.trackScope)}</section>`;
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

function sortHeader(key, label, params = parseRoute(location.hash).params, hint = '') {
  const active = params.sort === key;
  const next = nextSort(params, key);
  return `<th scope="col" aria-sort="${active ? params.dir === 'desc' ? 'descending' : 'ascending' : 'none'}"><button type="button" id="sort-${e(key)}" data-sort="${e(key)}" aria-label="${e(t.sortColumn(label,next.dir))}" ${hint ? `title="${e(hint)}"` : ''}>${e(label)}<span aria-hidden="true">${active ? params.dir === 'desc' ? '↓' : '↑' : '↕'}</span></button></th>`;
}

function disclosure(kind, id, name, before = '') {
  return `tabindex="0" data-kind="${e(kind)}" data-id="${e(id)}" data-before="${e(before)}" aria-expanded="false" aria-label="${e(t.toggleRow(name))}"`;
}

const chevronHeader = '<th class="chevron-cell" aria-hidden="true"></th>';
const chevronCell = '<td class="chevron-cell"><span class="row-chevron" aria-hidden="true">⌄</span></td>';

function raceSort(params = parseRoute(location.hash).params) {
  return params.sort ? params : {sort: raceOrder(params) === 'result' ? 'placing' : '', dir:'asc'};
}

function raceTable(entries, order = 'program', form = {}, toto = null) {
  const sort = raceSort();
  const columns = [['number',t.number],['name',t.horse],['form',t.priorForm],['driver',t.driver],['distance',t.distance],['odds',t.winOdds],['placing',t.placing],['time',t.kmTime],['prize',t.prize]];
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.racecard)}"><table class="runner-table"><thead><tr>${columns.map(([key,label])=>sortHeader(key,label,sort,key==='form'?t.formSort:'')).join('')}${chevronHeader}</tr></thead><tbody>${orderEntries(entries,sort,form,toto).map(r => `<tr class="expandable ${r.absent ? 'scratched' : isWinner(r) ? 'winner' : ''}" ${disclosure('horse',r.horseId,r.horseName,currentRace.meeting.date)} data-runner="${e(r.horseId)}" data-entry="${e(JSON.stringify(r))}"><td><div class="number-cell"><span class="program-number">${e(r.programNumber)}</span></div></td><td>${link('horse',{id:r.horseId,returnTo:returnContext(location.hash)},e(r.horseName),'horse-name')}<small>${e(t.trainer)}: ${personLink(r,'trainer')}</small><small class="equipment">${e(equipmentText(r))}</small></td><td class="form-cell">${recentForm(form[r.horseId])}</td><td>${personLink(r,'driver')}</td><td class="numeric">${e(r.distance || t.unknown)}</td>${oddsCell(r,toto)}<td><span class="place ${isWinner(r)?'first':''}">${e(r.absent?t.absent:resultText(r,'placing',t.unknown))}</span></td><td class="numeric">${e(kilometerTime(r,t.unknown))}</td><td class="numeric">${hasResult(r)&&r.price!=null&&r.price!==''?`${e(r.price)} €`:t.unknown}</td>${chevronCell}</tr>`).join('')}</tbody></table></div>`;
}

function raceDetail(data, calendarContext = {}) {
  const {meeting:m,race:r,races,entries} = data;
  return `<div class="selected-heading"><div><h2>${e(trackName(m))}</h2><p>${e(dateText(m.date,{weekday:'long'}))} · ${e(m.name||'')}</p></div>${venueLink(m)}</div>
    ${m.canceled?badge(t.canceled,'warning'):''}<nav class="race-tabs" aria-label="${e(t.raceHeading)}">${races.map(item=>link('calendar',calendarParams(calendarContext,m,item.number),e(t.race(item.number)),item.number===r.number?'selected':'')).join('')}</nav>
    <section class="race-detail"><div class="race-heading"><div><h2>${e(t.race(r.number))} <span>${e(r.data.plannedTime?t.at(r.data.plannedTime):'')}</span></h2><p>${e(raceMeta(r))} · ${e(r.entry_count===null?t.noUpdate:t.entries(entries.length))}</p></div>${badge(r.has_results?t.results:r.field_fetched_at?t.racecard:t.incomplete)}</div>
    <div id="race-table">${r.field_fetched_at===null?empty(t.noField,''):!entries.length?empty(t.emptyField,''):raceTable(entries,'program',data.form,data.toto)}</div>
    <div class="table-footer">${note(t.formHint+' '+t.resultHint+' '+t.oddsHint)}${totoStatus(data.toto)}${freshness(r.field_fetched_at)}</div></section>`;
}

function originBack(returnTo) {
  if (!returnTo) return '';
  const back = horseReturnRoute(returnTo);
  const labels = {people:t.backPeople,horses:t.backHorses,horse:t.backHorse,person:t.backPerson,party:t.backParty,saved:t.backSaved,calendar:t.backCalendar,race:t.backRace,tracks:t.backTracks,track:t.backTrack};
  return link(back.name,back.params,`${icon('back')}${e(labels[back.name])}`,'back-link');
}

function selectFilter(name, label, values, selected = '') {
  return `<label>${e(label)}<select name="${e(name)}">${values.map(([value,text])=>`<option value="${e(value)}" ${value===selected?'selected':''}>${e(text)}</option>`).join('')}</select></label>`;
}

function directoryToolbar(kind, params, breeds = []) {
  const horses = kind === 'horses';
  return `<form class="directory-toolbar" id="directory-filter" data-route="${kind}"><label class="compact-search">${e(horses?t.search:t.searchPerson)}<input id="directory-query" type="search" name="q" value="${e(params.q||'')}" placeholder="${e(horses?t.searchPlaceholder:t.searchAllPeople)}" maxlength="200"></label>
    ${horses?`${selectFilter('breed',t.breed,[['',t.allBreeds],...breeds.map(b=>[b,t.breeds[b]||b])],params.breed)}${selectFilter('gender',t.gender,[['',t.allGenders],...Object.entries(t.genders)],params.gender)}<label>${e(t.minAge)}<input type="number" name="min_age" min="0" max="60" value="${e(params.min_age||'')}"></label><label>${e(t.maxAge)}<input type="number" name="max_age" min="0" max="60" value="${e(params.max_age||'')}"></label><label class="check-filter"><input type="checkbox" name="upcoming" value="1" ${params.upcoming==='1'?'checked':''}>${e(t.onlyUpcoming)}</label>`
    :`${selectFilter('role',t.role,[['all',t.allRoles],['driver',t.driver],['trainer',t.trainer],['owner',t.owners],['breeder',t.breeders]],params.role||'all')}${selectFilter('activity',t.activity,[['',t.allActivity],['past',t.pastActivity],['upcoming',t.upcoming]],params.activity)}`}
    <button class="button primary">${e(t.searchButton)}</button>${link(kind,{},e(t.clearFilters),'text-link')}</form>`;
}

function directoryTable(rows, kind, params) {
  const horses = kind==='horses';
  const columns = horses?[['name',t.horse],['breed',t.breed],['age',t.age],['gender',t.gender],['entries',t.entriesShort],['last_date',t.lastStart],['next_date',t.nextStart]]:[['name',t.name],['role',t.role],['horses',t.horses],['entries',t.entriesShort],['last_date',t.lastStart],['next_date',t.nextStart]];
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(horses?t.horses:t.people)}"><table class="directory-table"><thead><tr>${columns.map(([k,l])=>sortHeader(k,l,params)).join('')}${chevronHeader}</tr></thead><tbody>${rows.map(r=>{
    const target = horses?'horse':['owner','breeder'].includes(r.role)?'party':'person';
    const name = r.name||t.unnamedPerson(r.id);
    return `<tr class="expandable" ${disclosure(horses?'horse':r.role,r.id,name)}><td><div class="identity-cell">${link(target,{id:r.id,...(!horses?{role:r.role}:{}),returnTo:returnContext(location.hash)},e(name),'horse-name')}</div></td>${horses?`<td>${e(t.breeds[r.breed]||r.breed||t.unknown)}</td><td class="numeric">${e(r.age??t.unknown)}</td><td>${e(t.genders[r.gender]||r.gender||t.unknown)}</td>`:`<td>${e(t[r.role])}</td><td class="numeric">${e(r.horses)}</td>`}<td class="numeric">${e(r.entries??(horses?0:t.unknown))}</td><td>${r.last_date?e(dateText(r.last_date)):t.unknown}</td><td>${r.next_date?e(dateText(r.next_date)):t.unknown}</td>${chevronCell}</tr>`;
  }).join('')}</tbody></table></div>`;
}

async function directoryView(kind, params) {
  const data = await api(`directory/${kind}`,{...params,today:localDay(new Date(overview.now))});
  return `<div class="directory-heading">${header(t[kind])}<span role="status">${e(t.directoryCount(data.total))}</span></div>${directoryToolbar(kind,params,data.breeds)}
    ${data.rows.length?directoryTable(data.rows,kind,params):empty(t.noMatches,t.noMatchesHint)}${peoplePagination(kind,params,data,t.peoplePages)}
    ${note(kind==='people'?t.directoryScope:t.historyHint)}`;
}

async function horsesView(params) { return directoryView('horses',params); }

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

async function peopleView(params) { return directoryView('people',params); }

function activityToolbar(params, data, includeHorses = false) {
  const {name} = parseRoute(location.hash);
  return `<div class="activity-controls"><nav class="segmented" aria-label="${e(t.activity)}">${['upcoming','history',...(includeHorses?['horses']:[])].map(period=>link(name,{...params,period,offset:0,sort:'',dir:''},`${e(period==='horses'?t.relatedHorses:period==='upcoming'?t.upcomingShort:t.historyShort)} (${e(period==='horses'?data.summary.horses:period==='upcoming'?data.summary.upcoming:data.summary.entries-data.summary.upcoming)})`,period===data.period?'selected':'')).join('')}</nav>
    ${data.period!=='horses'?`<form id="activity-filter" class="activity-filter">${selectFilter('track',t.track,[['',t.allTracks],...Object.entries(overview.tracks)],params.track)}<button class="button">${e(t.apply)}</button></form>`:''}</div>`;
}

function activityTable(rows, params, {horse = false, preview = false, role = ''} = {}) {
  const upcoming = params.period==='upcoming';
  const columns = [['date',t.date],...(!horse?[['name',t.horse]]:[]),['track',t.meeting],['number',t.number],['distance',t.distance],...(role==='driver'?[]:[['driver',t.driver]]),...(role==='trainer'?[]:[['trainer',t.trainer]]),...(upcoming?[['status',t.entryStatus]]:[['placing',t.placing],['time',t.kmTime],['prize',t.prize]])];
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.history)}"><table class="activity-table"><thead><tr>${columns.map(([key,label])=>preview?`<th scope="col">${e(label)}</th>`:sortHeader(key,label,params)).join('')}${preview?'':chevronHeader}</tr></thead><tbody>${rows.map(s=>`<tr ${preview?'':`class="expandable" ${disclosure('horse',s.horse_id,s.data.horseName,s.date)}`} data-entry="${e(JSON.stringify(s.data))}"><td><div class="identity-cell">${e(dateText(s.date))}</div><small>${e(s.race_data?.plannedTime||'')}</small></td>${horse?'':`<td>${link('horse',{id:s.horse_id,returnTo:returnContext(location.hash)},e(s.data.horseName),'horse-name')}</td>`}<td>${link('race',{date:s.date,track:s.track,number:s.race_number,returnTo:returnContext(location.hash)},`${e(s.meeting_data.formattedTrackName||s.city||s.track)}<small>${e(t.race(s.race_number))}${s.data.startType&&s.data.startType!=='TOTO'?` · ${e(t.types[s.data.startType]||s.data.startType)}`:''}</small>`,'horse-name')}${s.meeting_data.canceled?badge(t.canceled,'warning'):''}</td><td class="numeric">${e(s.program_number)}</td><td class="numeric">${e(s.data.distance||t.unknown)}</td>${role==='driver'?'':`<td>${personLink(s.data,'driver')}</td>`}${role==='trainer'?'':`<td>${personLink(s.data,'trainer')}</td>`}<td>${e(s.absent?t.absent:upcoming?t.entered:resultText(s.data,'placing',t.unknown))}</td>${upcoming?'':`<td class="numeric">${e(kilometerTime(s.data,t.unknown))}</td><td class="numeric">${hasResult(s.data)&&s.prize!=null&&s.prize!==''?`${e(s.prize)} €`:t.unknown}</td>`}${preview?'':chevronCell}</tr>`).join('')}</tbody></table></div>`;
}

function linkedHorseTable(rows, params, sortable = false) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.relatedHorses)}"><table><thead><tr>${[['name',t.horse],['entries',t.entriesShort],['last_date',t.lastStart],['next_date',t.nextStart]].map(([k,l])=>sortable?sortHeader(k,l,params):`<th scope="col">${e(l)}</th>`).join('')}${chevronHeader}</tr></thead><tbody>${rows.map(h=>`<tr class="expandable" ${disclosure('horse',h.id,h.name)}><td><div class="identity-cell">${link('horse',{id:h.id,returnTo:returnContext(location.hash)},e(h.name),'horse-name')}</div></td><td>${e(h.entries??t.unknown)}</td><td>${h.last_date?e(dateText(h.last_date)):t.unknown}</td><td>${h.next_date?e(dateText(h.next_date)):t.unknown}</td>${chevronCell}</tr>`).join('')}</tbody></table></div>`;
}

function activityContent(data, params, horse = false) {
  return `${activityToolbar(params,data,!horse)}${data.rows.length?(data.period==='horses'?linkedHorseTable(data.rows,params,true):activityTable(data.rows,{...params,period:data.period},{horse,role:horse?'':params.role})):empty(data.period==='upcoming'?t.noUpcoming:t.noHistory,'')}${peoplePagination(parseRoute(location.hash).name,{...params,period:data.period},data,t.startPages)}`;
}

async function personView(params) {
  const data = await api('activity',{...params,today:localDay(new Date(overview.now))});
  const p = data.person, s = data.summary;
  return `${originBack(params.returnTo||route('people',{role:p.role}))}<div class="profile-identity">${photoFigure(data.photo,p.name)}${header(p.name||t.unnamedPerson(p.id),'',e(t[p.role]),freshness(p.fetched_at))}</div>
    <div class="summary-strip"><span>${e(t.inArchive)}</span>${stats([[s.horses,t.horsesLabel],[s.entries,t.startsLabel],[s.results,t.resultsLabel],[s.wins,t.winsLabel]])}</div>
    ${activityContent(data,params)}${note(t.personScope+' '+t.relationshipScope)}<div class="detail-toolbar">${source()}</div>`;
}

function relatedHorseTable(horses, returnTo, sortable = false) {
  const headers = [['name',t.horse],['observed',t.observedRelationship]].map(([key,label])=>sortable?sortHeader(key,label):`<th scope="col">${e(label)}</th>`).join('');
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${e(t.relatedHorses)}"><table><thead><tr>${headers}${chevronHeader}</tr></thead><tbody>${horses.map(h=>`<tr class="expandable" ${disclosure('horse',h.id,h.name)}><td><div class="identity-cell">${link('horse',{id:h.id,returnTo:returnContext(returnTo)},e(h.name),'horse-name')}</div></td><td>${e(timestamp(h.relationship_fetched_at))}</td>${chevronCell}</tr>`).join('')}</tbody></table></div>`;
}

async function partyView(params) {
  const data = await api('party',params);
  const p = data.party;
  const back = personReturnRoute(params.returnTo,p.role);
  const labels = {people:t.backPeople,horse:t.backHorse,party:t.backParty,person:t.backPerson,race:t.backRace,calendar:t.backCalendar,saved:t.backSaved};
  return `${link(back.name,back.params,`${icon('back')}${e(labels[back.name])}`,'back-link')}${header(p.name,'',e(t[p.role]),freshness(p.fetched_at))}${note(t.partyScope + ' ' + t.profileScope)}
    <div class="section-heading"><h2>${e(t.partyHorses)} · ${e(data.total)}</h2></div>
    ${relatedHorseTable(data.horses,route('party',{...params,offset:data.offset}),true)}${peoplePagination('party',params,data,t.peoplePages)}`;
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
  return `<section class="offspring-section"><div class="section-heading"><h2>${e(t.offspring)} · ${e(data.total)}</h2></div>${data.horses.length ? relatedHorseTable(data.horses,route('horse',{...params,offspring_offset:data.offset}),true) : `<p>${e(t.noOffspring)}</p>`}${data.total>data.limit ? `<nav class="pagination" aria-label="${e(t.offspringPages)}">${data.offset ? page(Math.max(0,data.offset-data.limit)) : '<span></span>'}<span>${e(t.page(data.offset+1,Math.min(data.offset+data.limit,data.total),data.total))}</span>${data.offset+data.limit<data.total ? page(data.offset+data.limit) : '<span></span>'}</nav>` : ''}</section>`;
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
  const family = params.section==='family';
  const data = await api('horse',{...params,section:family?'family':'activity'});
  const h = data.horse;
  const breed = data.profile?.data.breedFinName||t.breeds[h.breed]||h.breed||t.unknown;
  const activity = family?null:await api('activity',{...params,role:'horse',today:localDay(new Date(overview.now))});
  return `${originBack(params.returnTo||route('horses'))}<div class="profile-identity">${photoFigure(data.photo,h.name)}${header(h.name,'',`${e(breed)} · ${e(h.country||t.unknown)}`,saveButton(h.id))}</div><div id="save-feedback" role="status"></div>
    <nav class="profile-tabs" aria-label="${e(t.fullHorse)}">${link('horse',{...params,section:'activity',sort:'',dir:''},e(t.activity),family?'':'selected')}${link('horse',{...params,section:'family',sort:'',dir:''},e(t.family),family?'selected':'')}</nav>
    ${family?`${horseBackground(data)}${offspringSection(data.offspring,params)}`:`<div class="summary-strip"><span>${e(t.inArchive)}</span>${stats([[activity.summary.entries,t.startsLabel],[activity.summary.results,t.resultsLabel],[activity.summary.wins,t.winsLabel]])}</div><div class="horse-activity-layout"><section>${activityContent(activity,params,true)}</section><aside class="horse-facts">${profileFacts(data)}</aside></div>`}
    ${note([t.profileScope,t.historyHint,t.pedigreeHint,t.offspringHint].join(' '))}<div class="detail-toolbar">${freshness(h.fetched_at)}${source()}</div>`;
}

function profileFacts(data) {
  const p = data.profile?.data;
  if (!p) return `<h3>${e(t.profileTitle)}</h3><p>${e(t.profileNotCollected)}</p>`;
  return `<h3>${e(t.profileTitle)}</h3><dl><dt>${e(t.born)}</dt><dd>${p.birthDate?e(dateText(p.birthDate)):t.unknown}${p.birthDateAccurate===false?`<small>${e(t.birthApproximate)}</small>`:''}</dd><dt>${e(t.gender)}</dt><dd>${e(t.genders[p.gender]||p.gender||t.unknown)}${p.dead?` · ${e(t.dead)}`:''}</dd>${['owner','breeder'].map(role=>{const ref=data.parties.find(x=>x.role===role);return `<dt>${e(t[role])}</dt><dd>${ref?link('party',{role,id:ref.id,returnTo:returnContext(location.hash)},e(ref.label),'person-link'):t.unknown}</dd>`}).join('')}</dl>${freshness(data.profile.fetched_at)}`;
}

function submitFilters(form) {
  if (!form.reportValidity()) return;
  const {name,params} = parseRoute(location.hash);
  const values = Object.fromEntries(new FormData(form));
  const next = form.id==='directory-filter'?{...values,sort:params.sort||'',dir:params.dir||''}:{...params,...values,offset:'0'};
  for (const key of Object.keys(next)) if (next[key]==='') delete next[key];
  const destination = route(form.dataset.route||name,next);
  if (destination===location.hash) render(false);
  else location.hash=destination;
}

function bind() {
  const calendar = document.querySelector('#calendar-filter');
  calendar?.addEventListener('submit',event=>{
    event.preventDefault();
    const prior = parseRoute(location.hash).params;
    const params = {...(prior.sort?{sort:prior.sort,dir:prior.dir||'asc'}:{order:raceOrder(prior)}),...Object.fromEntries(new FormData(calendar))};
    calendar.elements.to.setCustomValidity(params.to<params.from?t.invalidRange:'');
    if (calendar.reportValidity()) location.hash=route('calendar',params);
  });
  calendar?.addEventListener('input',()=>calendar.elements.to.setCustomValidity(''));
  calendar?.querySelector('select')?.addEventListener('change',()=>calendar.requestSubmit());
  for (const form of document.querySelectorAll('#directory-filter,#activity-filter')) {
    form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(searchTimer);submitFilters(form);});
    form.addEventListener('change',event=>{if(event.target.matches('select,[type="checkbox"]')){clearTimeout(searchTimer);submitFilters(form);}});
    form.addEventListener('input',event=>{
      if (!event.target.matches('input:not([type="checkbox"])')||event.isComposing) return;
      clearTimeout(searchTimer);
      generation++; controller?.abort();
      searchTimer=setTimeout(()=>submitFilters(form),250);
    });
    form.addEventListener('compositionend',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>submitFilters(form),250);});
  }
  document.querySelector('#retry')?.addEventListener('click',()=>render(true));
}

function previewHistory(starts) {
  return starts.length?activityTable(starts,{}, {horse:true,preview:true}):`<p>${e(t.noHistory)}</p>`;
}

async function readPreview(kind, id, before = '') {
  const key = [kind,id,before,overview.last_fetched_at].join(':');
  const cached = previewCache.get(key);
  if(cached&&Date.now()-cached.time<30000) return cached.data;
  const data = await api('preview',{kind,id,today:localDay(new Date(overview.now)),...(before?{before}:{})});
  if(previewCache.size>=80) previewCache.delete(previewCache.keys().next().value);
  previewCache.set(key,{time:Date.now(),data});
  return data;
}

function personPreviewContent(data) {
  const p=data.person,s=data.summary;
  return `${photoFigure(data.photo,p.name,true)}<div class="preview-summary">${e(t.inArchive)} · ${e(s.horses)} ${e(t.horsesLabel.toLowerCase())} · ${e(s.entries)} ${e(t.startsLabel.toLowerCase())}</div><h4>${e(data.period==='upcoming'?t.upcoming:t.history)}</h4>${data.rows.length?activityTable(data.rows,{period:data.period}, {preview:true,role:p.role}):`<p>${e(t.noHistory)}</p>`}${link('person',{id:p.id,role:p.role,returnTo:returnContext(location.hash)},e(t.fullPerson),'text-link')}`;
}

function compactPerson(data, role, entry) {
  const heading = `<h4>${e(t[role])} · ${personLink(entry,role)}</h4>`;
  if (!data) return `<section class="compact-person">${heading}<p>${e(t.error)}</p></section>`;
  const summary=data.summary;
  return `<section class="compact-person">${heading}${photoFigure(data.photo,data.person.name,true)}<p class="preview-metrics">${e(t.sampleSummary(summary.entries,summary.results,summary.wins))}</p><h5>${e(data.period==='upcoming'?t.upcoming:t.latestStarts)}</h5><ul class="compact-starts">${data.rows.slice(0,3).map(s=>`<li><span>${e(dateText(s.date,{day:'numeric',month:'numeric'}))}</span>${link('horse',{id:s.horse_id,returnTo:returnContext(location.hash)},e(s.data.horseName))}<span>${e(s.city||s.track)} · ${e(t.race(s.race_number))}</span><strong>${e(s.absent?t.absent:data.period==='upcoming'?(s.race_data?.plannedTime||t.unknown):resultText(s.data,'placing',t.unknown))}</strong></li>`).join('')}</ul></section>`;
}

function compactHorse(data, entry) {
  const p=data.profile?.data;
  const facts=[p?.birthDate?`${e(t.born)} ${e(dateText(p.birthDate))}`:'',p?.gender?e(t.genders[p.gender]||p.gender):'',entry?e(equipmentText(entry)):''].filter(Boolean);
  const parties=data.parties.map(ref=>`${e(t[ref.role])}: ${link('party',{role:ref.role,id:ref.id,returnTo:returnContext(location.hash)},e(ref.label))}`);
  return `<div class="compact-horse">${photoFigure(data.photo,data.horse.name,true)}<strong>${link('horse',{id:data.horse.id,returnTo:returnContext(location.hash)},e(data.horse.name))}</strong>${facts.map(f=>`<span>${f}</span>`).join('')}${parties.map(f=>`<span>${f}</span>`).join('')}</div>`;
}

let previewSerial=0;
async function toggleDetails(row) {
  if(row.getAttribute('aria-expanded')==='true') {
    row.nextElementSibling?.remove();row.setAttribute('aria-expanded','false');row.removeAttribute('aria-controls');row.classList.remove('expanded');return;
  }
  row.setAttribute('aria-expanded','true');row.classList.add('expanded');
  const preview=document.createElement('tr');preview.className='horse-preview';preview.id=`preview-${++previewSerial}`;
  row.setAttribute('aria-controls',preview.id);
  const span=row.children.length;
  preview.innerHTML=`<td colspan="${span}"><div role="status">${e(t.loading)}</div></td>`;row.after(preview);
  preview.style.setProperty('--preview-width',`${Math.max(220,row.closest('.table-scroll').clientWidth-34)}px`);
  const {kind,id,before}=row.dataset;
  const entry=row.dataset.entry?JSON.parse(row.dataset.entry):null;
  const roles=entry?['driver','trainer'].filter(role=>personReference(entry,role)):[];
  try {
    const [data,...people]=await Promise.all([readPreview(kind,id,before),...roles.map(role=>readPreview(role,personReference(entry,role).id).catch(()=>null))]);
    if(!preview.isConnected) return;
    let content;
    if(kind==='horse') {
      const starts=data.activity.rows;
      content=`${compactHorse(data,entry)}<div class="runner-preview-layout ${starts.length?'':'without-history'}"><section class="horse-recent"><h4>${e(t.previewHistory)}</h4>${previewHistory(starts)}${row.dataset.runner?marketHistory(id):''}</section>${roles.map((role,i)=>compactPerson(people[i],role,entry)).join('')}</div>`;
    } else if(['driver','trainer'].includes(kind)) content=personPreviewContent(data);
    else content=`<p>${e(t.partyScope)}</p>${relatedHorseTable(data.horses,location.hash)}${link('party',{role:kind,id,returnTo:returnContext(location.hash)},e(t.fullPerson),'text-link')}`;
    preview.innerHTML=`<td colspan="${span}"><div class="preview-content">${content}</div></td>`;
  } catch(error) {
    if(error.name!=='AbortError'&&preview.isConnected) preview.innerHTML=`<td colspan="${span}"><div role="alert">${e(t.error)} <button type="button" class="button retry-preview">${e(t.retry)}</button></div></td>`;
  }
}

function sortTable(button) {
  const {name,params}=parseRoute(location.hash);
  const next={...params,...nextSort(name==='calendar'?raceSort(params):params,button.dataset.sort)};
  delete next.order;
  if(name!=='calendar') next.offset='0';
  if(name==='horse'&&params.section==='family')next.offspring_offset='0';
  if(!next.sort){delete next.sort;delete next.dir;}
  if(name!=='calendar'){location.hash=route(name,next);return;}
  history.replaceState(null,'',route(name,next));
  const table=document.querySelector('#race-table table'),body=table.tBodies[0];
  const rows=new Map([...body.querySelectorAll(':scope > tr[data-runner]')].map(row=>[row.dataset.runner,{row,preview:row.nextElementSibling?.classList.contains('horse-preview')?row.nextElementSibling:null}]));
  for(const entry of orderEntries(currentRace.entries,raceSort(next),currentRace.form,currentRace.toto)) {
    const item=rows.get(entry.horseId);body.append(item.row);if(item.preview)body.append(item.preview);
  }
  for(const control of table.querySelectorAll('[data-sort]')) {
    const key=control.dataset.sort,active=next.sort===key;
    control.closest('th').setAttribute('aria-sort',active?next.dir==='desc'?'descending':'ascending':'none');
    control.querySelector('span').textContent=active?next.dir==='desc'?'↓':'↑':'↕';
    control.setAttribute('aria-label',t.sortColumn(control.childNodes[0].textContent,nextSort(next,key).dir));
  }
  document.querySelectorAll('.race-tabs a,.quick-races a,.meeting-select,.week-arrow,#calendar-filter .segmented a,.meeting-browser .pagination a').forEach(anchor=>{
    const target=parseRoute(anchor.hash);delete target.params.order;delete target.params.sort;delete target.params.dir;
    if(next.sort)Object.assign(target.params,{sort:next.sort,dir:next.dir});anchor.href=route(target.name,target.params);
  });
}

app.addEventListener('click',event=>{
  const sort=event.target.closest('[data-sort]');if(sort){sortTable(sort);return;}
  const save=event.target.closest('[data-save]');
  if(save) {
    try {
      const ids=toggleSaved(localStorage,save.dataset.save);
      if(parseRoute(location.hash).name==='saved')render(true);
      else {const active=ids.includes(save.dataset.save);save.setAttribute('aria-pressed',String(active));save.textContent=active?t.removeSaved:t.saveHorse;document.querySelector('#save-feedback').textContent=active?t.savedDone:t.savedRemoved;}
    } catch(error){document.querySelector('#save-feedback').textContent=error.message==='limit'?t.savedLimit:t.savedErrorHint;}
    return;
  }
  const retry=event.target.closest('.retry-preview');
  if(retry){const row=retry.closest('tr.horse-preview').previousElementSibling;toggleDetails(row);toggleDetails(row);return;}
  if(event.target.closest('a,button,input,select,label,summary,details')||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||window.getSelection()?.toString())return;
  const row=event.target.closest('tr.expandable');
  if(row)toggleDetails(row);
});

app.addEventListener('keydown',event=>{
  const row=event.target;
  if(row.matches('tr.expandable')&&['Enter',' '].includes(event.key)) {
    event.preventDefault();toggleDetails(row);
  }
});

async function render(focus = false) {
  controller?.abort();
  controller = new AbortController();
  const turn = ++generation;
  clearTimeout(searchTimer);
  if(parseRoute(location.hash).name==='race') history.replaceState(null,'',calendarRaceRoute(parseRoute(location.hash).params));
  const { name, params } = parseRoute(location.hash);
  const nextRoute = { name, params };
  const inPlace = sameView(renderedRoute, nextRoute);
  if (!document.querySelector('#main')) shell(name);
  const main = document.querySelector('#main');
  const active = document.activeElement;
  const selection = active.matches('input[type=search]') ? [active.selectionStart,active.selectionEnd] : null;
  const focusKey = { id: active.id, href: active.getAttribute('href'), name: active.getAttribute('name'),
    label: active.textContent,
    region: active.closest('.race-tabs') ? '.race-tabs' : active.closest('.quick-races') ? '.quick-races'
      : active.closest('.pagination') ? '.pagination' : '' };
  const datesOpen = document.querySelector('.custom-dates')?.open;
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
  try {
    const freshOverview = await api('overview');
    if (turn !== generation) return;
    overview = freshOverview;
    const views = { calendar: calendarView, meeting: meetingView, tracks: tracksView, track: trackView, horses: horsesView, horse: horseView, saved: savedView, coverage: coverageView, people: peopleView, person: personView, party: partyView };
    if (!views[name]) throw Object.assign(new Error('Unknown page'), { status: 404 });
    const content = await views[name](params);
    if (turn !== generation) return;
    renderedRoute = nextRoute;
    main.innerHTML = content;
    main.removeAttribute('aria-busy');
    if (!inPlace) main.style.minHeight = '';
    const section = ['meeting','race'].includes(name) ? 'calendar'
      : name === 'track' ? 'tracks' : name === 'horse' ? 'horses' : ['person','party'].includes(name) ? 'people' : name;
    document.querySelectorAll('.nav-link').forEach(el => {
      const selected = parseRoute(el.hash).name === section;
      el.classList.toggle('active', selected);
      if (selected) el.setAttribute('aria-current','page');
      else el.removeAttribute('aria-current');
    });
    document.title = `${document.querySelector('h1').textContent} · ${t.brand}`;
    bind();
    if (inPlace) {
      const dates = document.querySelector('.custom-dates'); if(dates) dates.open=!!datesOpen;
      for (const {selector,x,y} of scrolls) {
        const el = document.querySelector(selector);
        if (el) { el.scrollLeft = x; el.scrollTop = y; }
      }
      const target = focusKey.id ? document.getElementById(focusKey.id)
        : focusKey.href ? [...main.querySelectorAll(focusKey.region ? `${focusKey.region} a` : 'a')].find(el => el.getAttribute('href') === focusKey.href
          || (focusKey.region === '.pagination' && el.textContent === focusKey.label))
        : focusKey.name ? [...main.querySelectorAll('[name]')].find(el => el.name === focusKey.name) : null;
      if (target) { target.focus({preventScroll:true}); if(selection&&target.type==='search')target.setSelectionRange(...selection); }
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
window.addEventListener('resize',()=>{for(const preview of document.querySelectorAll('tr.horse-preview'))preview.style.setProperty('--preview-width',`${Math.max(220,preview.closest('.table-scroll').clientWidth-34)}px`);});
window.addEventListener('hashchange', () => render(true));
document.querySelector('.skip').addEventListener('click', event => {
  event.preventDefault();
  document.querySelector('#main').focus();
});
render();
