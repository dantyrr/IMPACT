# Weekly Auto-Update — Design

Date: 2026-08-18
Status: approved

## Problem

Updating the IMPACT site is manual: `run_weekly_update.py` then `upload_to_r2.py`.
Between 2026-06-22 and 2026-08-17 nobody ran them, and nothing signalled the
drift — the site served two-month-old data and the staleness was only found by
going looking for it. The goal is a weekly refresh that needs no human, plus an
alarm that fires when it silently stops working.

## Constraints

- `data/impact.db` is 65 GB and local to this Mac. GitHub-hosted runners have
  ~14 GB of disk, so the workflow suggested in CLAUDE.md cannot work. The job
  must run on the machine holding the database.
- A full run took 325 minutes on 2026-08-17, past the 6-hour GitHub job ceiling.
- The lid is normally closed, so the Mac is normally asleep. launchd does not
  wake a sleeping machine; it defers the job until the next wake.
- The Mac is on battery on Sunday nights, so `pmset repeat wakeorpoweron` will
  not fire: a sleeping MacBook on battery with the lid shut ignores scheduled
  wakes. The schedule is therefore anchored to Monday morning at the office,
  where the machine is reliably awake and on AC power.
- Secrets already exist in `.env` and must not be duplicated.

## Architecture

    pmset repeat wakeorpoweron U 21:55  (wakes the Mac)
        |
    launchd com.impact.weekly-update    (Sunday 22:00)
        |
    scripts/weekly_auto_update.sh       (re-execs under caffeinate)
        |-- run_weekly_update.py --days 14
        |-- upload_to_r2.py             (only if the update succeeded)
        `-- writes log, status file, notifies on failure

    launchd com.impact.freshness-check  (daily 10:00)
        `-- scripts/check_update_freshness.sh — notifies if data > 9 days old

The scheduled wake and the launchd agent are deliberately separate: the wake is
a system-level power event needing admin rights, set once by hand; the agent is
per-user and owned by this repo.

## Components

### scripts/weekly_auto_update.sh

Sequences the pipeline and reports on it. Exists because launchd provides no
working directory, no `PATH` to conda, and no `.env`.

- Re-execs itself under `caffeinate -i -m -s` so the machine stays awake for
  the whole run. Guarded by an env var so the re-exec happens once.
- Pins the interpreter to `/Users/dtyrrell/miniconda3/bin/python`.
- Takes a lock (atomic `mkdir`) and additionally refuses to start if a
  `run_weekly_update.py` is already running, however it was launched. Two
  writers on one SQLite database is the failure this prevents.
- Runs the update with `--days 14`. A 7-day cadence with a 10-day window leaves
  3 days of slack; one missed run becomes a permanent hole. 14 days gives a
  full week of overlap, and re-scanning known papers is cheap.
- Decides whether it is due from the day of week, not a flat interval. A run
  takes ~5.5h, so a Monday-morning start records success in the afternoon; a
  flat 7-day test would miss the following Monday morning by hours and drift
  later every week. Mondays therefore use a 5-day threshold, other days 9.
- Uploads only when the update exits zero, so a partial run cannot publish over
  good data.
- Appends to `logs/weekly-update-YYYY-MM-DD.log`, prunes logs older than 8 weeks.
- Writes `data/last_update_status.json` on every outcome.
- `--dry-run` exercises the whole path without touching data.
- Pings `HEALTHCHECK_URL` on success if that variable is set in `.env`; absent,
  the step is skipped. Hook for an external dead-man's switch later.

### scripts/check_update_freshness.sh

The dead-man's switch. A job that never runs cannot report its own failure, so
something outside it must notice the silence. Reads
`data/last_update_status.json` daily and notifies if the last success is older
than 9 days (one cadence plus two days of slack), or if the file is missing.

Local rather than an external service: no account, no credential, no network.
Its limit is that it only reaches the user at the machine — which is also the
only place they could act on it.

### launchd agents

- `com.impact.weekly-update` — Monday 08:00, 08:45, 10:00, 14:00 (the primary
  window, around plugging in at the office), plus daily 11:00 and 16:00 as the
  travel-week failsafe. Every one of these is a no-op unless the data is due.
- `com.impact.freshness-check` — daily 10:00.

Both keep `RunAtLoad` false. Plists are versioned in `deploy/launchd/` and
symlinked into `~/Library/LaunchAgents/`, so the schedule is reviewable in git.

## Failure handling

| Failure | Detection | Result |
|---|---|---|
| Update exits non-zero | wrapper checks exit code | upload skipped, notification, status records phase |
| Upload exits non-zero | wrapper checks exit code | notification; data is correct locally, retried next week |
| Concurrent run | lock dir + pgrep | second run exits immediately, logs the reason |
| Individual API batches fail | retry with backoff in the Python | PMIDs written to `data/failed_pmids_*.txt` |
| Mac asleep at check time | launchd defers to next wake | runs when the lid opens |
| Monday missed (travel, holiday) | 9-day fallback threshold | runs on any later day |
| Due but on battery | `pmset -g ps` check | defers until AC, or until 12 days stale |
| Mac off / wake failed / agent unloaded | freshness check | notification once data passes 9 days |
| Sleep mid-run | `caffeinate -i -m -s` | prevented while the job holds the assertion |

Known gap: if the Mac is never plugged in during a check window, runs defer
until the 12-day threshold and then attempt 5.5 hours on battery, which may not
survive to completion. The freshness check catches the aftermath.

## Testing

1. `weekly_auto_update.sh --dry-run` — env loading, locking, logging, status
   file, notification path, without touching data.
2. Concurrency guard: invoke while a real update runs; expect immediate exit.
3. `check_update_freshness.sh` against a backdated status file; expect a
   notification. Then against a current one; expect silence.
4. `launchctl kickstart -k gui/$UID/com.impact.weekly-update` for a real run
   under launchd's environment, which is where `PATH` and `.env` problems show.
5. `pmset -g sched` confirms the repeating wake.

## Out of scope

- Committing or pushing `index.json`. Git history stays under manual control.
- Author affiliation backfill (`fetch_author_data.py`), still run by hand.
- Moving the pipeline off this machine.
