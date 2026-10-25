import test from 'node:test';
import assert from 'node:assert/strict';
import { photoFigure, handlePhotoError } from '../hippos_analyst/web/photos.mjs';

const photo = {url:`/media/${'a'.repeat(64)}.jpg`, width:640, height:480,
  source_url:'https://commons.wikimedia.org/wiki/File:Horse.jpg',
  license_url:'https://creativecommons.org/licenses/by-sa/4.0/',
  author:'<img onerror=alert(1)>', title:'Horse & driver', license:'CC BY-SA 4.0',
  description:'<script>alert(1)</script>', thumbnail:true};

test('photos keep attribution, source and licence while escaping provider text', () => {
  const html=photoFigure(photo,'Horse <one>');
  assert.ok(html.includes('CC BY-SA 4.0'));
  assert.ok(html.includes(photo.source_url));
  assert.ok(html.includes(photo.license_url));
  assert.ok(html.includes('&lt;img onerror=alert(1)&gt;'));
  assert.ok(html.includes('Horse &lt;one&gt;'));
  assert.ok(!html.includes('<script>'));
});

test('missing, external and executable image URLs never create remote images', () => {
  for (const entry of [null,{...photo,url:'https://example.com/horse.jpg'},
    {...photo,url:'/media/../../secret.jpg'},{...photo,license_url:'javascript:alert(1)'},
    {...photo,source_url:'https://commons.wikimedia.org.evil.example/photo'}]) {
    assert.ok(!photoFigure(entry,'Subject').includes('<img'));
    assert.equal(photoFigure(entry,'Subject',true),'');
  }
});

test('failed image loads reveal fallback and preserve the credit figure', () => {
  const fallback={hidden:true};
  const image={tagName:'IMG',hidden:false,closest:()=>true,parentElement:{querySelector:()=>fallback}};
  handlePhotoError({target:image});
  assert.equal(image.hidden,true);
  assert.equal(fallback.hidden,false);
  handlePhotoError({target:{tagName:'DIV'}});
});
