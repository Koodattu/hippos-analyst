import {escapeHtml as e, route} from './model.mjs';
import {fi as t} from './locales/fi.mjs';

// Natural Earth 1:110m Admin 0, v5.1.2, Finland. Public domain.
// Geographic coordinates and markers share a plate carree projection,
// with longitude scaled at 65 degrees north. See docs/tracks.md.
const FINLAND_RINGS = [[[28.59193,69.06478],[28.44594,68.36461],[29.97743,67.6983],[29.05459,66.94429],[30.21765,65.80598],[29.54443,64.94867],[30.44468,64.20445],[30.03587,63.55281],[31.51609,62.86769],[31.13999,62.35769],[30.21111,61.78003],[28.07,60.50352],[28.07,60.50352],[28.07,60.50352],[26.25517,60.42396],[24.49662,60.05732],[22.8697,59.84637],[22.29076,60.39192],[21.32224,60.72017],[21.54487,61.70533],[21.05921,62.60739],[21.53603,63.18973],[22.44274,63.81781],[24.73051,64.90234],[25.39807,65.11143],[25.29404,65.53435],[23.90338,66.00693],[23.56588,66.39605],[23.53947,67.93601],[21.97854,68.61685],[20.64559,69.10625],[21.24494,69.37044],[22.35624,68.84174],[23.66205,68.89125],[24.73568,68.64956],[25.68921,69.09211],[26.17962,69.8253],[27.73229,70.16419],[29.01557,69.76649],[28.59193,69.06478]]];

export function projectTrack(coordinates) {
  if (!coordinates) return null;
  const {latitude, longitude} = coordinates;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)
      || latitude < 59.5 || latitude > 70.5 || longitude < 19 || longitude > 32) return null;
  return {x: 280 + (longitude - 26) * Math.cos(65 * Math.PI / 180) * 54,
    y: 30 + (70.3 - latitude) * 54};
}

export function trackMarkers(tracks) {
  const points = tracks.flatMap(track => {
    const position = projectTrack(track.coordinates);
    return position ? [{...position, id:track.id, name:track.name,
      label:track.city || track.name, labelY:position.y-12}] : [];
  });
  // Keep names centered above their dots; lift crowded labels by one text row.
  const placed = [];
  for (const point of [...points].sort((a,b) => b.y-a.y)) {
    let overlap;
    do {
      overlap = placed.find(other => Math.abs(point.x-other.x) < (point.label.length+other.label.length)*3.8+4
        && Math.abs(point.labelY-other.labelY) < 18);
      if (overlap) point.labelY = overlap.labelY-18;
    } while (overlap);
    placed.push(point);
  }
  return points;
}

export function trackMap(tracks, returnTo) {
  const markers = trackMarkers(tracks);
  const outline = FINLAND_RINGS.map(ring => ring.map(([longitude,latitude],index) => {
    const {x,y} = projectTrack({latitude,longitude});
    return `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ')+' Z').join(' ');
  return `<aside class="track-map-panel" aria-labelledby="track-map-heading">
    <div class="track-map-heading"><h1 id="track-map-heading">${e(t.tracks)}</h1><span>${e(t.tracksMapped(markers.length))}</span></div>
    <svg class="finland-map" viewBox="100 0 360 670" role="group" aria-labelledby="track-map-heading" aria-describedby="track-map-help">
      <path class="finland-outline" d="${outline}" aria-hidden="true"/>
      ${markers.map(point => `<a class="track-map-marker" href="${e(route('track',{id:point.id,returnTo}))}" aria-label="${e(t.mapTrackLabel(point.label,point.name))}">
          <title>${e(point.label)} · ${e(point.name)}</title>
          <circle class="track-map-hit" cx="${point.x}" cy="${point.y}" r="13"/>
          <circle class="track-map-dot" cx="${point.x}" cy="${point.y}" r="5"/>
          <text x="${point.x}" y="${point.labelY}" text-anchor="middle">${e(point.label)}</text>
        </a>`).join('')}
    </svg>
    <p id="track-map-help" class="track-map-help">${e(t.trackMapHelp)}${markers.length<tracks.length ? ` ${e(t.tracksNotMapped(tracks.length-markers.length))}` : ''}</p>
    <a class="track-map-credit" href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">${e(t.trackMapCredit)}</a>
  </aside>`;
}
