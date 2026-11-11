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
  return {x: 280 + (longitude - 26) * Math.cos(65 * Math.PI / 180) * 72,
    y: 30 + (70.3 - latitude) * 72};
}

const overlaps = (a,b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
const around = (x,y,r) => ({left:x-r, right:x+r, top:y-r, bottom:y+r});

// Try spots beside the pin first, then fan out. Reserve the space occupied by
// text, dots and connectors so later labels leave a clear path back to each pin.
function placeLabel(point, width, occupied, dots) {
  let best, bestCost = Infinity;
  for (let radius=7; radius<=290 && radius<bestCost; radius+=7) {
    for (let step=0; step<16; step++) {
      const angle = step*Math.PI/8;
      const dx = Math.cos(angle), dy = Math.sin(angle);
      const endX = point.x + radius*dx, endY = point.y + radius*dy;
      const labelX = endX + (Math.abs(dx)<0.05 ? -width/2 : dx>0 ? 2 : -width-2);
      const labelY = endY + (Math.abs(dy)<0.05 ? 0 : Math.sign(dy)*8.5);
      const box = {left:labelX-2,right:labelX+width+2,top:labelY-9,bottom:labelY+9};
      if (box.left<2 || box.right>510 || box.top<12 || box.bottom>838) continue;
      if (occupied.some(other=>overlaps(box,other)) || dots.some(dot=>overlaps(box,dot))) continue;
      const path = [];
      let conflicts = 0;
      for (let distance=6; distance<radius; distance+=2) {
        const sample = around(point.x+dx*distance,point.y+dy*distance,1.25);
        if (occupied.some(other=>overlaps(sample,other)) || dots.some(dot=>overlaps(sample,dot))) conflicts++;
        path.push(sample);
      }
      const cost = radius + conflicts*250;
      if (cost < bestCost) {
        bestCost = cost;
        best = {labelX,labelY,endX,endY,leader:radius>7,box,path,cost};
      }
    }
  }
  return best;
}

export function trackMarkers(tracks, measure = label => label.length*7.5) {
  const points = tracks.flatMap(track => {
    const position = projectTrack(track.coordinates);
    return position ? [{...position, id:track.id, name:track.name, label:track.city || track.name}] : [];
  });
  const dots = points.map(p=>around(p.x,p.y,4.5));
  // Try crowded locations first. Give the hardest placements first choice on
  // the next pass, keeping the arrangement with the fewest conflicts.
  const order = points.map(point=>({point,width:measure(point.label),
    priority:points.filter(q=>Math.hypot(q.x-point.x,q.y-point.y)<38).length}));
  let bestCost = Infinity;
  let bestLayout = new Map();
  for (let pass=0; pass<4; pass++) {
    const occupied = [], layout = new Map();
    let total = 0;
    order.sort((a,b)=>b.priority-a.priority || a.point.id.localeCompare(b.point.id));
    for (const item of order) {
      const label = placeLabel(item.point,item.width,occupied,dots);
      item.priority = label?.cost ?? 1000000;
      total += item.priority ** 2;
      if (!label) continue;
      const {box,path,cost,...position} = label;
      layout.set(item.point.id,position);
      occupied.push(box,...path);
    }
    if (total < bestCost) {
      bestLayout = layout;
      bestCost = total;
    }
  }
  return points.map(point=>({...point,...bestLayout.get(point.id)}));
}

export function trackMap(tracks, returnTo) {
  const context = typeof document !== 'undefined' && document.createElement('canvas').getContext('2d');
  if (context) context.font = '550 13px ' + getComputedStyle(document.documentElement).fontFamily;
  const markers = trackMarkers(tracks,context ? label=>context.measureText(label).width : undefined);
  const outline = FINLAND_RINGS.map(ring => ring.map(([longitude,latitude],index) => {
    const {x,y} = projectTrack({latitude,longitude});
    return `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ')+' Z').join(' ');
  return `<aside class="track-map-panel" aria-labelledby="track-map-heading">
    <div class="track-map-heading"><h1 id="track-map-heading">${e(t.tracks)}</h1><span>${e(t.trackCount(tracks.length))}</span></div>
    <svg class="finland-map" viewBox="0 8 512 834" role="group" aria-labelledby="track-map-heading">
      <path class="finland-outline" d="${outline}" aria-hidden="true"/>
      ${markers.map(point => `<a class="track-map-marker" href="${e(route('track',{id:point.id,returnTo}))}" aria-label="${e(t.mapTrackLabel(point.label,point.name))}">
          <title>${e(point.label)} · ${e(point.name)}</title>
          ${point.leader ? `<line class="track-map-leader" x1="${point.x}" y1="${point.y}" x2="${point.endX}" y2="${point.endY}"/>` : ''}
          <circle class="track-map-hit" cx="${point.x}" cy="${point.y}" r="9"/>
          <circle class="track-map-dot" cx="${point.x}" cy="${point.y}" r="4"/>
          ${point.labelX != null ? `<text x="${point.labelX}" y="${point.labelY}" dominant-baseline="central">${e(point.label)}</text>` : ''}
        </a>`).join('')}
    </svg>
  </aside>`;
}
