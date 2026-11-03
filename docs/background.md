# Standalone continuous worker

The owner requested a standalone process on 2 November 2026. The hourly/sign-in
Windows task has been removed. No Windows service, startup entry or Codex task is
installed. The worker runs independently of Codex and the local web UI, and must
be started again manually after reboot, sign-out or termination.

## Start

Foreground (Ctrl+C stops it):

```powershell
python -m hippos_analyst.background --continuous --delay 15 --daily-budget 1000 --db data/hippos.sqlite3
```

Windowless, from this workspace:

```powershell
$workerProcess = Start-Process -FilePath 'C:\Python311\pythonw.exe' -WindowStyle Hidden -PassThru -WorkingDirectory 'E:\Projektit\hippos-analyst' -ArgumentList '-m hippos_analyst.background --continuous --delay 15 --daily-budget 1000 --db "E:\Projektit\hippos-analyst\data\hippos.sqlite3"'
$workerProcess.Id
```

The current process was started using that command. The OS worker lock prevents
another manual or background collector from running concurrently. It is retained
through batch boundaries, idle sleeps, cooldowns and daily-budget waits.

## Limits and behaviour

- **15 seconds** minimum between request starts and **1,000 attempts per UTC day**,
  explicitly raised from 500 on 3 November at the owner's request.
  Attempts already made today, including failures, count toward this cap.
- Repeated batches permit up to 20 refresh, ten profile and ten history requests.
  There is no hourly delay between batches and no borrowing unused phase shares.
- When the daily cap is reached, the process stays alive without network traffic
  until UTC midnight. It counts a new day from timestamps, never by resetting data.
- Each pass computes the current Europe/Helsinki date. Race refresh covers three
  days back through seven ahead, with a minimum observation age of 24 hours.
- Five new known race-participant profiles per Helsinki day, two ancestor generations;
  completed profiles are not automatically refreshed and ancestor stubs do not seed roots.
- Historical collection proceeds one month at a time from the contiguous October
  2026 frontier. Twelve consecutive empty months persist a pause and stop the worker.
- Access refusal, rate limiting, redirect, schema error, failed job or persistent
  pause stops the process. No stop or failed job is automatically cleared/retried.
- A transient error ends the batch; a new batch can start only after the stored
  Retry-After/cooldown and at least 60 seconds. Five consecutive transient failures
  persist a stop. Idle batches wait 60 seconds rather than busy-looping.
- Only the existing four Hippos endpoint families and allowlists are used. No extra
  Toto polling, person/owner enumeration or unbounded ancestry. See [scope](backfill.md).

Without `--continuous`, the module still runs one bounded pass. Its defaults, and
those of the existing `maintain` CLI, remain 30 seconds and 200 attempts/day.
No third-party dependencies were added.

## Logs and stop controls

- `data/hippos.background.log`: UTC timestamps, process PID, selected limits,
  plans, requests, waits, outcomes and counts. Rotates at 2 MB with four backups.
- `data/hippos.background.json`: atomic checkpoint after each pass, including PID,
  mode, limits, counts, stop state and integrity result. It is a checkpoint, not a
  process-liveness probe; during a run/wait consult the log and live process too.
- `data/hippos.worker.pid`: launch PID for this manually started worker; may become
  stale after process exit. Verify the process identity before acting on a PID.
- The coverage UI and `python -m hippos_analyst status` read the live archive.

```powershell
Get-Content data/hippos.background.log -Tail 25
python -m hippos_analyst status
python -m hippos_analyst pause --reason 'Stopped by operator'
```

`pause` is the graceful stop: an in-flight request may finish, then no further
requests start. Budget/idle/cooldown waits check the pause at least every 30 seconds.
After investigating a stop and explicitly deciding to resume, use the existing
`resume` command and manually launch the worker again. Resume respects cooldown;
failed jobs still require individually reviewed retries. No auto-restart exists.

## Verification

135 Python tests passed. Coverage includes actual local wrapper passes with fake
upstream responses, Helsinki date rollover, 15-second spacing across multiple
passes, a second process blocked by the lock, 500- and 1,000-attempt exhaustion, UTC-midnight
recovery without resetting the ledger, lock retention during waits, operator stop,
Retry-After, 403/429/redirect/schema stops, failed jobs and unexpected local errors.
The twelve-empty-month test verifies no request or new scheduling at that boundary.
Live launch verified the standalone process making successful requests. It was
left running; this does not claim all archive history has been collected.
