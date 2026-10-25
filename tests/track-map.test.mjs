import test from 'node:test';
import assert from 'node:assert/strict';
import {projectTrack, trackMarkers, trackMap} from '../hippos_analyst/web/track-map.mjs';

const venue = (id, latitude, longitude) => ({id, name:id, city:id, coordinates:{latitude,longitude}});

test('map projection preserves north/east directions and rejects missing or out-of-region positions', () => {
  const helsinki = projectTrack({latitude:60.216332,longitude:24.839744});
  const tornio = projectTrack({latitude:65.8,longitude:24.2});
  const joensuu = projectTrack({latitude:62.6,longitude:29.7});
  assert.ok(tornio.y < helsinki.y);
  assert.ok(joensuu.x > helsinki.x);
  assert.deepEqual(projectTrack({latitude:70.3,longitude:26}),{x:280,y:30});
  for (const value of [null,{}, {latitude:null,longitude:25}, {latitude:NaN,longitude:25},
    {latitude:60,longitude:Infinity}, {latitude:0,longitude:0}, {latitude:71,longitude:25}]) {
    assert.equal(projectTrack(value),null);
  }
});

test('markers retain their geographic positions and track identities', () => {
  const tracks = Array.from({length:17},(_,i)=>venue(String(i),60+i*0.03,i%2 ? 25 : 27));
  const points = trackMarkers(tracks);
  assert.equal(points.length,17);
  for (const point of points) {
    const position = projectTrack(tracks.find(track=>track.id===point.id).coordinates);
    assert.deepEqual({x:point.x,y:point.y},position);
    assert.equal(point.label,point.id);
    assert.ok(point.labelY <= point.y-12);
  }
});

test('map links preserve directory context and escape source labels; unavailable positions stay unplotted', () => {
  const track = {...venue('hippos-H',60.216332,24.839744),city:'<script>',name:'"Vermo"'};
  const html = trackMap([track,{id:'missing',name:'Missing'}],'#/tracks?q=Vermo');
  assert.ok(html.includes('id=hippos-H&amp;returnTo=%23%2Ftracks%3Fq%3DVermo'));
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.equal((html.match(/class="track-map-dot"/g)||[]).length,1);
  assert.equal(trackMarkers([{id:'missing'}]).length,0);
  assert.ok(!trackMap([],'#/tracks').includes('class="track-map-dot"'));
});
