"""Explicitly curated Commons photos. Browsing never fetches remote media."""

import hashlib
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

from .api import NoRedirects

MAX_BYTES = 8 * 1024 * 1024
KINDS = ('horse', 'driver', 'trainer')
LICENSES = {f'CC {kind.upper()} {version}': f'https://creativecommons.org/licenses/{kind}/{version}/'
            for kind in ('by', 'by-sa') for version in ('2.0', '2.5', '3.0', '4.0')}
LICENSES['CC0'] = 'https://creativecommons.org/publicdomain/zero/1.0/'


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, text):
        self.parts.append(text)


def plain(value):
    parser = PlainText()
    parser.feed(str(value))
    return ' '.join(' '.join(parser.parts).split())[:4000]


def identity(kind, entity_id):
    if kind not in KINDS or not isinstance(entity_id, str) or not re.fullmatch(r'[0-9]{1,30}', entity_id):
        raise ValueError('Select a horse, driver or trainer with an exact string ID')


def verify_target(db, kind, entity_id, expected_name):
    identity(kind, entity_id)
    if kind == 'horse':
        row = db.execute('SELECT name FROM horses WHERE id=?', (entity_id,)).fetchone()
        actual = row['name'] if row else None
    else:
        from .server import Archive
        try:
            actual = Archive(db).person(kind, entity_id, '9999-12-31')['person']['name']
        except LookupError:
            actual = None
    if not actual or actual != expected_name:
        raise ValueError('Target name does not match this archive ID; verify the identity before importing')


def jpeg_size(body):
    """Read dimensions without a production imaging dependency; reject other media."""
    if not 4 < len(body) <= MAX_BYTES or not body.startswith(b'\xff\xd8') or not body.endswith(b'\xff\xd9'):
        raise ValueError('Expected a complete JPEG of at most 8 MiB')
    offset = 2
    while offset + 4 <= len(body):
        if body[offset] != 255:
            break
        offset += 1
        while offset < len(body) and body[offset] == 255:
            offset += 1
        if offset >= len(body):
            break
        marker = body[offset]
        offset += 1
        if marker in (0xD9, 0xDA):
            break
        length = int.from_bytes(body[offset:offset + 2], 'big')
        if length < 2 or offset + length > len(body):
            break
        if marker in (0xC0, 0xC1, 0xC2):
            if length < 8:
                break
            height = int.from_bytes(body[offset + 3:offset + 5], 'big')
            width = int.from_bytes(body[offset + 5:offset + 7], 'big')
            if not 0 < width <= 16000 or not 0 < height <= 16000 or width * height > 40_000_000:
                break
            return width, height
        offset += length
    raise ValueError('Unsupported or malformed JPEG dimensions')


def checked_url(url, hosts):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username or parsed.password
            or parsed.port not in (None, 443)):
        raise ValueError('Unexpected media source URL')
    return url


def fetch(url, content_type):
    # No automatic redirects, retries, cookies or credentials, including on refusal.
    request = Request(url, headers={'User-Agent': 'HipposAnalyst/0.1 (private educational photo import)',
                                   'Accept': content_type})
    with build_opener(NoRedirects()).open(request, timeout=30) as response:
        if response.headers.get_content_type() != content_type:
            raise ValueError('Unexpected photo response content type')
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError('Photo response exceeds 8 MiB')
    return body


def commons_metadata(payload):
    try:
        return _commons_metadata(payload)
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError('Unexpected Commons metadata structure') from exc


def _commons_metadata(payload):
    pages = payload.get('query', {}).get('pages', {})
    if len(pages) != 1:
        raise ValueError('Expected one Commons file')
    page = next(iter(pages.values()))
    info = page.get('imageinfo', [])
    if page.get('imagerepository') != 'local' or len(info) != 1:
        raise ValueError('Commons image is missing')
    info = info[0]
    meta = info.get('extmetadata', {})
    value = lambda key: plain(meta.get(key, {}).get('value', ''))
    license_name = value('LicenseShortName')
    license_url = value('LicenseUrl')
    if license_name not in LICENSES or license_url.rstrip('/') != LICENSES[license_name].rstrip('/'):
        raise ValueError('Image does not have a supported, explicit CC licence')
    if value('Restrictions') or value('Permission'):
        raise ValueError('Image has additional conditions; review it separately')
    author = value('Artist')
    if not author or info.get('mime') != 'image/jpeg':
        raise ValueError('Expected a credited JPEG photo')
    source_url = checked_url(info['descriptionurl'], {'commons.wikimedia.org'})
    original_url = checked_url(info['url'], {'upload.wikimedia.org'})
    download_url = checked_url(info.get('thumburl', original_url), {'upload.wikimedia.org', 'thumb.wikimedia.org'})
    return {'title': page['title'], 'author': author, 'credit': value('Credit'),
            'attribution': value('Attribution'), 'license': license_name, 'license_url': LICENSES[license_name],
            'source_url': source_url, 'original_url': original_url, 'download_url': download_url,
            'description': value('ImageDescription'), 'file_timestamp': info.get('timestamp'),
            'thumbnail': 'thumburl' in info, 'retrieved_at': time.time()}


def import_commons(db, kind, entity_id, expected_name, title, identity_note, replace=False, fetcher=fetch):
    """Two bounded GETs for one reviewed file; exact ID assignment, never name matching."""
    verify_target(db, kind, entity_id, expected_name)
    if not isinstance(identity_note, str) or not 10 <= len(identity_note.strip()) <= 2000:
        raise ValueError('Record how the pictured subject was verified against this archive ID')
    if not isinstance(title, str) or not title.startswith('File:') or not 6 < len(title) <= 240 or '|' in title:
        raise ValueError('Supply one exact Commons File: title')
    existing = db.execute('SELECT asset_hash FROM profile_photos WHERE kind=? AND entity_id=?', (kind, entity_id)).fetchone()
    if existing and not replace:
        raise ValueError('A photo is already assigned; use --replace only for an intentional replacement')
    url = 'https://commons.wikimedia.org/w/api.php?' + urlencode({
        'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'titles': title,
        'iiprop': 'url|extmetadata|size|mime|timestamp', 'iiurlwidth': 640})
    metadata = commons_metadata(json.loads(fetcher(url, 'application/json')))
    body = fetcher(metadata['download_url'], 'image/jpeg')
    width, height = jpeg_size(body)
    digest = hashlib.sha256(body).hexdigest()
    # Recheck immediately before the atomic write, in case the racing archive changed.
    with db:
        db.execute('BEGIN IMMEDIATE')
        verify_target(db, kind, entity_id, expected_name)
        if not replace and db.execute('SELECT 1 FROM profile_photos WHERE kind=? AND entity_id=?', (kind, entity_id)).fetchone():
            raise ValueError('A photo was assigned during import; existing work was preserved')
        db.execute('INSERT OR IGNORE INTO photo_assets VALUES(?,?,?,?,?)',
                   (digest, body, width, height, json.dumps(metadata, ensure_ascii=False)))
        db.execute('INSERT INTO profile_photos VALUES(?,?,?,?,?) ON CONFLICT(kind,entity_id) DO UPDATE SET '
                   'asset_hash=excluded.asset_hash,expected_name=excluded.expected_name,identity_note=excluded.identity_note',
                   (kind, entity_id, digest, expected_name, identity_note.strip()))
        db.execute('DELETE FROM photo_assets WHERE NOT EXISTS (SELECT 1 FROM profile_photos WHERE asset_hash=sha256)')
    return get(db, kind, entity_id)


def get(db, kind, entity_id):
    identity(kind, entity_id)
    row = db.execute('SELECT a.sha256,a.width,a.height,a.metadata FROM profile_photos p '
                     'JOIN photo_assets a ON a.sha256=p.asset_hash WHERE p.kind=? AND p.entity_id=?',
                     (kind, entity_id)).fetchone()
    if not row:
        return None
    metadata = json.loads(row['metadata'])
    return {key: metadata[key] for key in ('title', 'author', 'credit', 'attribution', 'license', 'license_url',
                                         'source_url', 'description', 'thumbnail')} | {
        'url': f"/media/{row['sha256']}.jpg", 'width': row['width'], 'height': row['height']}


def image(db, path):
    match = re.fullmatch(r'/media/([a-f0-9]{64})\.jpg', path)
    if not match:
        raise LookupError('Photo not found')
    row = db.execute('SELECT image FROM photo_assets WHERE sha256=?', (match[1],)).fetchone()
    if not row:
        raise LookupError('Photo not found')
    return row['image']


def remove(db, kind, entity_id):
    identity(kind, entity_id)
    with db:
        count = db.execute('DELETE FROM profile_photos WHERE kind=? AND entity_id=?', (kind, entity_id)).rowcount
        db.execute('DELETE FROM photo_assets WHERE NOT EXISTS (SELECT 1 FROM profile_photos WHERE asset_hash=sha256)')
    return count
