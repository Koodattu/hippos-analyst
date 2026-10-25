# Horse and people photos

Implemented 25 October 2026. Horse, driver and trainer profiles and expanded rows
show locally stored photos, with photographer, licence and expandable source
details. Images retain their framing. Missing photos have a quiet profile
placeholder; missing preview photos are omitted. A failed image load shows a
translated fallback without removing the credit.

## Import a reviewed Commons photo

Review the actual file page, caption and subject before importing. Select the
exact archive ID and role, and copy the name displayed by the archive. A filename
or matching surname alone is not sufficient identity evidence. Owner/breeder
name groups are deliberately unsupported: they can represent several people.

```powershell
python -m hippos_analyst import-commons-photo --kind horse --id 1176323680446942215 --name 'Tekno Odin*' --file 'File:Tekno Odin & Øystein Tjomsland.jpg' --identity-note 'Named Norwegian cold-blooded trotter in Commons; archive profile identifies Tekno Odin, born 2008-05-10, sire Moe Odin, dam Lyana.'
```

The command performs two bounded GETs: Commons metadata and one JPEG, requesting
a thumbnail. It supports explicit CC BY and CC BY-SA 2.0/2.5/3.0/4.0 and CC0
licences with matching licence URLs, and requires photographer attribution.
Unrecognised licences or additional restriction fields stop the import. This
validation does not replace reviewing the identity or a file-page dispute.

Only Commons metadata and Wikimedia image hosts are accepted. There are no
redirects, account credentials, retries, crawling or automatic name matches.
Responses are capped at 8 MiB; JPEG dimensions are bounded. The importer reads
JPEG headers, not a full image decoder; browser verification confirms rendering.

Imports share the database's worker lock with the racing collectors. They do not
clear or change Hippos/Toto stops, enqueue racing work, or contact those providers.
Commons imports are explicit one-file operations, not scheduled collection.

An existing assignment is preserved unless `--replace` is supplied. Invalid
metadata or failed downloads leave it intact. To remove an assignment offline:

```powershell
python -m hippos_analyst remove-photo --kind horse --id 1176323680446942215
```

## Storage and serving

`photo_assets` stores the JPEG bytes, SHA-256, dimensions and source metadata in
SQLite. `profile_photos` assigns an asset to `(kind, exact string ID)` and records
the checked archive name and identity evidence. Driver and trainer assignments
are separate, even when their IDs coincide. Identical bytes are shared; replacing
or removing the final reference removes the unused asset atomically.

Horse/person reads, activity and preview responses include optional `photo`
metadata. `/media/{sha256}.jpg` serves only an imported asset, with JPEG content
type and `nosniff`. Browsing performs no external image requests; the existing
same-origin image CSP remains in force. Source and licence links open only when
the user follows them. Photo imports and images stay in the ignored local
database; a source checkout does not include these binary assets.

## Initial verified selection

Six images were imported into the working archive, assigned to nine profiles.
The linked Commons pages contain the original file, attribution and licence.
These are historical photographs, not current appearance guarantees.

| Subject | Archive ID | Assigned roles | Source / credit / licence |
| --- | --- | --- | --- |
| Tekno Odin* | 1176323680446942215 | Horse | [Photo](https://commons.wikimedia.org/wiki/File:Tekno_Odin_%26_%C3%98ystein_Tjomsland.jpg) · Eirik Stenhaug, Equus · CC BY 3.0 |
| Järvsöfaks* | 8994252717229104725 | Horse | [Photo](https://commons.wikimedia.org/wiki/File:J%C3%A4rvs%C3%B6faks_in_the_snow_2009-11-25_001.jpg) · Kanal 75 · CC BY 3.0 |
| Esa Holopainen | 1720825983957021407 | Driver, trainer | [Photo](https://commons.wikimedia.org/wiki/File:Esa_Holopainen.jpg) · Markus Kauppinen · CC BY-SA 4.0 |
| Tapio Perttunen | 2736826219786487133 | Driver, trainer | [Photo](https://commons.wikimedia.org/wiki/File:Tapio_Perttunen_at_Mikkeli.jpg) · Markus Kauppinen · CC BY-SA 4.0 |
| Tuomas Pakkanen | 2049000527740092354 | Driver, trainer | [Photo](https://commons.wikimedia.org/wiki/File:Tuomas_Pakkanen_at_Mikkeli.jpg) · Markus Kauppinen · CC BY-SA 4.0 |
| Antti Teivainen | 6925177551314408008 | Trainer | [Photo](https://commons.wikimedia.org/wiki/File:Antti_Teivainen_at_Mikkeli.jpg) · Markus Kauppinen · CC BY-SA 4.0 |

Other horses and people remain without a photo until a reviewed source is
assigned. Hippos/Heila images are not automatically imported: Hippos's
[gallery guidance](https://www.hippos.fi/hevoskasvatus/heila-jalostusjarjestelman-kuvagalleria-avautuu/)
requires photographer permission for public reuse. The inspected Toto runner
samples did not establish a portrait feed. Commercial data/photo feeds remain
research candidates, not configured integrations.

## Verification

```powershell
python -m unittest discover -s tests -v
node --test tests/ui.test.mjs tests/photos.test.mjs
node --check hippos_analyst/web/app.mjs
```

The implementation run passed 121 Python and 30 JavaScript tests, including
identity/role separation, source/licence rejection, atomic replacement, shared
asset removal, local HTTP image serving, escaped attribution and image fallback.
Browser checks covered real horse/person photos, source details and a keyboard-
expanded race entry at desktop and 390px phone width, without document overflow.
