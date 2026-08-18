#!/bin/bash
#
# Dead-man's switch for the weekly auto-update.
#
# A job that never runs cannot report its own failure, so something outside it
# has to notice the silence. Reads the status file the wrapper maintains and
# notifies when the last success is too old — which covers the cases no
# in-job alert can: the agent was unloaded, the Mac was off all week, the
# scheduled wake never happened.
#
# Invoked daily by launchd (com.impact.freshness-check).

set -uo pipefail

REPO="/Users/dtyrrell/Projects/IMPACT"
PYTHON="/Users/dtyrrell/miniconda3/bin/python"
STATUS="$REPO/data/last_update_status.json"
MAX_AGE_DAYS=9        # one cadence plus slack

notify() { /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 || true; }

if [ ! -f "$STATUS" ]; then
    notify "IMPACT data may be stale" "No update status file yet — has the weekly job ever run?"
    exit 0
fi

AGE=$("$PYTHON" - "$STATUS" <<'PY' 2>/dev/null || echo 999
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
)

if [ "$AGE" -ge "$MAX_AGE_DAYS" ]; then
    if [ "$AGE" -ge 999 ]; then
        notify "IMPACT data may be stale" "No successful update on record. Check logs/."
    else
        notify "IMPACT data is ${AGE} days old" "The weekly update has not succeeded since then. Check logs/."
    fi
fi
exit 0
