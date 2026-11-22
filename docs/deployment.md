# VM deployment

Run the web service on one Linux VM with Docker Engine and Compose v2.
It serves the Finnish UI, JSON API and media from the same origin. Gunicorn uses
one process for handling requests and two threads. The collector is independent.
The optional predictor uses the CatBoost 1.2.10 evaluation library and the same
versioned model used by the workstation. Train models separately.

## First start

From the checkout at `/srv/projects/hippos-analyst`:

```sh
docker compose --profile '*' config --quiet
docker compose build web
```

To bring across the existing archive, **restore it before starting web** using
the procedure below. To start with an empty archive, go straight to the next step.

```sh
docker compose up -d --no-build --wait web
curl -fsS http://127.0.0.1:8765/healthz
```

From the workstation run `ssh -L 8765:127.0.0.1:8765 vaarattu-server`, then
open `http://127.0.0.1:8765`. Only the VM loopback port is published. The site
has no application login. SSH controls access in this configuration.

The named volume `archive` is mounted at `/data` and survives application
rebuilds and container replacement. Use a local filesystem for Docker volumes.
SQLite WAL, shared memory and the single-collector lock require the same
filesystem on one host. Gunicorn initializes the archive before serving. HTTP
handlers open read-only SQLite connections. The volume is writable for schema
initialization and WAL bookkeeping. Never use `down -v` on the production stack.

## Move or restore an archive

1. At cutover, stop the workstation collector and prediction watcher and confirm
   they have exited. A persistent operator pause travels with the archive.
   For a rehearsal, take a live backup and leave VM collection disabled.
2. Run the backup tool on the source. Supply the versioned model directory to
   include its CBM and report. On the current Windows checkout:

   ```powershell
   python -m hippos_analyst.backup --db data/hippos.sqlite3 --output backups --model (Get-Content data/prediction-current-model.txt)
   ```

3. Transfer that ZIP privately to the VM. On the VM, set `BUNDLE` to its
   absolute path. Run this in the checkout against a **fresh, empty volume**.
   The command accepts a trusted ZIP produced by this project's backup tool.

   ```sh
   docker compose run --rm --no-deps -T -v "$BUNDLE:/restore.zip:ro" web python - <<'PY'
   from pathlib import Path
   from zipfile import ZipFile
   dest = Path('/data')
   if any(dest.iterdir()):
       raise SystemExit('Restore requires an empty data volume')
   with ZipFile('/restore.zip') as bundle:
       if 'hippos.sqlite3' not in bundle.namelist() or bundle.testzip() is not None:
           raise SystemExit('Invalid backup')
       bundle.extractall(dest)
   PY
   ```

4. Start web. Check a known race and its stored predictions, then inspect
   `docker compose exec web python -m hippos_analyst --db /data/hippos.sqlite3 status`.
   The main database contains jobs, limits, cooldowns, source snapshots and
   imported photos. The sibling prediction database retains existing forecasts.
   The ZIP carries the selected model's inference files. Keep original training
   snapshots separately if you need to reproduce training.

For a restore drill on the same VM, use a fresh Compose project name with
`docker compose -p hippos-restore ...` throughout and an unused `HIPPOS_PORT`.
Do not enable collection in a rehearsal.

## Collection and forecasts

Start exactly one collector after retiring the old one. Set `HIPPOS_DELAY` and
`HIPPOS_DAILY_BUDGET` in the checkout's ignored `.env` to select approved limits.
Compose defaults to 30 seconds and 200 attempts per UTC day. This is lower
than the workstation's documented 1 second and 10,000 attempts per day.
The deployed collector uses `--pace-budget`. At 10,000 attempts per UTC day it
spaces attempts at least 8.64 seconds apart, including after restart. Refresh
jobs run first in each maintenance pass. The shared ledger still counts retries
and manual requests toward the hard cap. Previously spent attempts can delay
the next slot.
On race day, the collector targets ten-minute refreshes from 30 minutes before
the first scheduled start until 90 minutes after the last. It lengthens that
interval on large cards or small budgets. Outside that window today's target
is hourly.
Continuous collection runs SQLite's full-archive quick and foreign-key checks
once per UTC day. The worker status records the time of the last successful
check. A one-off maintenance run still performs both checks.

```sh
docker compose up -d --no-build collector
docker compose ps -a
docker compose exec web tail -n 20 /data/hippos.background.log
```

The worker exits on a persistent pause or failure. It has no automatic restart
loop. To pause deliberately, run the following and allow an in-flight request
to finish. Investigate the stored reason and failed jobs before using `resume`
and `docker compose start collector`.

```sh
docker compose exec web python -m hippos_analyst --db /data/hippos.sqlite3 pause
```

For fresh forecasts, set `HIPPOS_MODEL` in `.env` to the restored directory's
**basename** under `/data/models`. The default is `active`. Existing stored
predictions can be displayed with the predictor stopped.
An unchanged field, runner probabilities and history counts retain the original
forecast. A small confirmation record tracks the latest check and field
observation for freshness. Scoring uses the original creation time.

```sh
docker compose build predictor
docker compose up -d --no-build predictor
docker compose logs --tail 20 predictor
```

For an update, build the enabled images first, then run
`docker compose --profile collect --profile predict up -d --no-build --wait`
with the profiles you operate. For a paused collector update only web and
predictor. `HIPPOS_IMAGE_TAG` can pin a release tag for both images. Roll back
by selecting the previous built tag and recreating the services with
`--no-build`. Retain a pre-upgrade backup for releases that change the schema.

## Backups and reboot

Create a dedicated host directory writable by container UID 10001. The
defaults keep seven compressed generations. Set `HIPPOS_BACKUP_DIR` to an
absolute path on the backup disk, and `HIPPOS_BACKUP_KEEP` for another retention
count. The command publishes a ZIP after all included files pass the backup
steps. It stages one uncompressed SQLite file at a time. Budget space for the
largest database plus the incoming ZIP as well as retained generations.

```sh
install -d -o 10001 -g 10001 -m 0700 ./backups
docker compose run --rm --no-deps -T backup
install -m 0644 deploy/systemd/hippos-backup.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hippos-backup.timer
```

Copy completed ZIPs to off-VM storage with your backup system. A successful
local timer alone provides no protection against VM disk loss. Monitor the
timer result, latest backup age, disk space and worker stop state independently
of the web health check.

Web and predictor restart with Docker. For an enabled collector that should
start once at boot, install `deploy/systemd/hippos-collector.service` in
`/etc/systemd/system/`, run `systemctl daemon-reload` and
`systemctl enable hippos-collector.service`. The unit respects saved pauses.

## Integration with the deployments project

The base Compose file follows Trepo's shared-image and private loopback
conventions. Lunch Recommendations likewise keeps the archive on a persistent
volume. The shared VM's Caddy, external ingress networks and update runner
belong to the separate **deployments** repository.

For a hostname, add a deployments override that clears web's `ports` with
`!reset []`, attaches only web to a dedicated external ingress network with
alias `hippos-web`, and sets `HIPPOS_TRUSTED_HOSTS` to the exact DNS name.
Attach shared Caddy to that network and reverse-proxy to `hippos-web:8765`.
For a private deployment, configure authentication at Caddy for every route.
The production site at `horse.koodattu.dev` permits anonymous browsing.
Register the checkout and merged Compose command with the
existing runner. If using the boot unit, set `COMPOSE_FILE` in the checkout's
`.env` to the same base and override paths so its command preserves ingress.
The source data and cached photos retain their respective rights and attribution.
The shared edge exposes the web service. Database files and worker controls are
accessible only to operators on the VM.
