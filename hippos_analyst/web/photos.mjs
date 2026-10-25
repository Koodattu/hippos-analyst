import { escapeHtml as e } from './model.mjs';
import { fi as t } from './locales/fi.mjs';

function external(url, host) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && parsed.hostname === host && !parsed.username && !parsed.password ? parsed.href : '';
  } catch { return ''; }
}

export function photoFigure(photo, name, compact = false) {
  if (!photo || !/^\/media\/[a-f0-9]{64}\.jpg$/.test(photo.url)) {
    return compact ? '' : `<div class="photo-placeholder">${e(t.noPhoto)}</div>`;
  }
  const source = external(photo.source_url, 'commons.wikimedia.org');
  const licence = external(photo.license_url, 'creativecommons.org');
  if (!source || !licence) return compact ? '' : `<div class="photo-placeholder">${e(t.noPhoto)}</div>`;
  return `<figure class="profile-photo${compact ? ' compact-photo' : ''}">
    <div class="photo-frame"><img src="${e(photo.url)}" alt="${e(t.photoOf(name))}" width="${Number(photo.width)||640}" height="${Number(photo.height)||480}" decoding="async" ${compact ? 'loading="lazy"' : ''}><span class="photo-error" hidden>${e(t.photoUnavailable)}</span></div>
    <figcaption>${e(t.photoCredit(photo.author))} · <a href="${e(licence)}" target="_blank" rel="noreferrer">${e(photo.license)}</a>
      <details><summary>${e(t.photoDetails)}</summary><a href="${e(source)}" target="_blank" rel="noreferrer">${e(photo.title)}</a>${photo.attribution ? `<p>${e(photo.attribution)}</p>` : ''}${photo.credit ? `<p>${e(photo.credit)}</p>` : ''}${photo.description ? `<p>${e(photo.description)}</p>` : ''}<p>${e(photo.thumbnail ? t.photoThumbnail : t.photoOriginal)}</p></details>
    </figcaption></figure>`;
}

export function handlePhotoError(event) {
  const img = event.target;
  if (img.tagName !== 'IMG' || !img.closest('.profile-photo')) return;
  img.hidden = true;
  const fallback = img.parentElement.querySelector('.photo-error');
  if (fallback) fallback.hidden = false;
}
