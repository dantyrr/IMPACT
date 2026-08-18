#!/bin/bash
#
# IMPACT weekly auto-update.
#
# Runs the incremental update and publishes to R2. Invoked by launchd
# (com.impact.weekly-update) several times a day with --if-due; it exits
# immediately unless the data is actually stale, so the frequent checks are
# nearly free. Checking often rather than firing at one fixed moment is
# deliberate: this machine is usually asleep on battery with the lid shut, so
# a fixed slot is regularly missed and launchd will not wake it.
#
# Usage:
#   weekly_auto_update.sh            # run now, unconditionally
#   weekly_auto_update.sh --if-due   # run only if data is stale (launchd)
#   weekly_auto_update.sh --dry-run  # exercise the plumbing, touch nothing

set -uo pipefail

REPO="/Users/dtyrrell/Projects/IMPACT"
PYTHON="/Users/dtyrrell/miniconda3/bin/python"
LOG_DIR="$REPO/logs"
LOCK_DIR="$REPO/data/.weekly_update.lock"
STATUS="$REPO/data/last_update_status.json"

DAYS=14           # lookback window; > cadence so a missed run self-heals
DUE_DAYS=7        # consider the data stale after this many days
FORCE_DAYS=10     # run even on battery once this stale
LOG_KEEP_DAYS=56

IF_DUE=0
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --if-due)  IF_DUE=1 ;;
        --dry-run) DRY_RUN=1 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

# Hold the machine awake for the whole run. Re-exec once, guarded by the env
# var so the caffeinate wrapper does not recurse.
if [ -z "${IMPACT_CAFFEINATED:-}" ]; then
    export IMPACT_CAFFEINATED=1
    exec /usr/bin/caffeinate -i -m -s "$0" "$@"
fi

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/weekly-update-$(date +%Y-%m-%d).log"

log()    { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
notify() { /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 || true; }

on_ac_power() { /usr/bin/pmset -g ps | /usr/bin/grep -q "AC Power"; }

# Days since the last successful run; 999 if never.
data_age_days() {
    "$PYTHON" - "$STATUS" <<'PY' 2>/dev/null || echo 999
import json, sys, datetime
try:
    with open(sys.argv[1]) as f:
        last = json.load(f).get("last_success")
    if not last:
        raise ValueError
    age = datetime.datetime.now() - datetime.datetime.fromisoformat(last)
    print(int(age.total_seconds() // 86400))
except Exception:
    print(999)
PY
}

write_status() {  # phase, exit_code, note
    "$PYTHON" - "$STATUS" "$1" "$2" "${3:-}" <<'PY' 2>/dev/null || true
import json, sys, os, datetime
path, phase, code, note = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
try:
    with open(path) as f:
        d = json.load(f)
except Exception:
    d = {}
now = datetime.datetime.now().isoformat(timespec="seconds")
d["last_run"] = now
d["last_phase"] = phase
d["last_exit_code"] = code
if note:
    d["last_note"] = note
if code == 0 and phase == "complete":
    d["last_success"] = now
with open(path, "w") as f:
    json.dump(d, f, indent=2)
PY
}

# ---- should we run at all? ------------------------------------------------
AGE=$(data_age_days)
if [ "$IF_DUE" = "1" ]; then
    if [ "$AGE" -lt "$DUE_DAYS" ]; then
        exit 0                      # not due; stay silent
    fi
    if ! on_ac_power && [ "$AGE" -lt "$FORCE_DAYS" ]; then
        log "due (${AGE}d) but on battery — deferring"
        exit 0
    fi
fi

# ---- one writer at a time -------------------------------------------------
if /usr/bin/pgrep -f "run_weekly_update.py" >/dev/null 2>&1; then
    log "an update is already running — exiting"
    exit 0
fi
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    if [ -f "$LOCK_DIR/pid" ] && ! /bin/kill -0 "$(cat "$LOCK_DIR/pid")" 2>/dev/null; then
        log "clearing stale lock from pid $(cat "$LOCK_DIR/pid")"
        rm -rf "$LOCK_DIR" && mkdir "$LOCK_DIR" 2>/dev/null
    else
        log "lock held — exiting"
        exit 0
    fi
fi
echo $$ > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

cd "$REPO" || { notify "IMPACT update failed" "cannot cd to $REPO"; exit 1; }

log "=== start (age ${AGE}d, $(on_ac_power && echo "AC" || echo "battery")${DRY_RUN:+, dry-run}) ==="
write_status "started" 0

# ---- phase 1: update ------------------------------------------------------
if [ "$DRY_RUN" = "1" ]; then
    "$PYTHON" scripts/run_weekly_update.py --days "$DAYS" --dry-run >> "$LOG" 2>&1
else
    "$PYTHON" scripts/run_weekly_update.py --days "$DAYS" >> "$LOG" 2>&1
fi
rc=$?
if [ $rc -ne 0 ]; then
    log "update FAILED (exit $rc) — skipping upload"
    write_status "update" $rc "see $LOG"
    notify "IMPACT update failed" "run_weekly_update.py exited $rc. Upload skipped."
    exit $rc
fi
log "update ok"

if [ "$DRY_RUN" = "1" ]; then
    log "dry-run: skipping upload"
    write_status "dry-run" 0
    log "=== done (dry-run) ==="
    exit 0
fi

# ---- phase 2: publish -----------------------------------------------------
"$PYTHON" scripts/upload_to_r2.py >> "$LOG" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
    log "upload FAILED (exit $rc)"
    write_status "upload" $rc "data is correct locally; retry upload_to_r2.py"
    notify "IMPACT upload failed" "upload_to_r2.py exited $rc. Local data is fine."
    exit $rc
fi
log "upload ok"

write_status "complete" 0
log "=== done ==="

# ---- optional external dead-man's switch ----------------------------------
HC_URL=$(/usr/bin/grep -E '^HEALTHCHECK_URL=' "$REPO/.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ')
if [ -n "${HC_URL:-}" ]; then
    /usr/bin/curl -fsS -m 10 "$HC_URL" >/dev/null 2>&1 || log "healthcheck ping failed"
fi

/usr/bin/find "$LOG_DIR" -name 'weekly-update-*.log' -mtime +$LOG_KEEP_DAYS -delete 2>/dev/null
exit 0
