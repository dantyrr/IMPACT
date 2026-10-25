#!/usr/bin/env python3
"""
Long-lived holder of the weekly-update lock for a multi-day rebuild.

scripts/weekly_auto_update.sh uses the directory data/.weekly_update.lock as
its mutex: it mkdirs it, and if that fails and $LOCK_DIR/pid names a dead
process it clears the lock as stale, otherwise it logs "lock held" and exits.
A rebuild runs as several separate processes with pauses for review, so one
long-lived process holds the lock for the whole rebuild with its own pid in
`pid`; the wrapper then never sees it as stale.

Usage:
    nohup python scripts/rebuild_lock.py hold > rebuild_lock.log 2>&1 &
                                            # blocks until SIGTERM/SIGINT; ignores SIGHUP
    python scripts/rebuild_lock.py release  # SIGTERM the holder (only if owner == rebuild)
    python scripts/rebuild_lock.py status   # print pid / owner / alive

    --lock-dir PATH overrides the default <repo>/data/.weekly_update.lock.

Exit-code contract (other tooling calls `status` as a precondition):
    status: 0 if a live `rebuild` holder exists, 1 otherwise.
    hold:   1 if the lock is already held by a live pid.
    release: 1 if there is no lock or its owner is not `rebuild`.
"""

import argparse
import os
import shutil
import signal
import sys
import threading
from pathlib import Path

OWNER = "rebuild"
DEFAULT_LOCK_DIR = Path(__file__).resolve().parent.parent / "data" / ".weekly_update.lock"


def _read(lock_dir, name):
    try:
        return (lock_dir / name).read_text().strip()
    except OSError:
        return None


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _holder(lock_dir):
    """Return (pid or None, owner or None, alive)."""
    raw = _read(lock_dir, "pid")
    pid = int(raw) if raw and raw.isdigit() else None
    return pid, _read(lock_dir, "owner"), bool(pid and _pid_alive(pid))


def _write_atomic(path, text):
    """Write via temp file + rename so `path` is only ever absent or complete.

    The weekly wrapper treats a present-but-empty pid file as a dead pid and
    clears the lock, so a truncate-then-write window is not acceptable.
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def cmd_hold(lock_dir):
    # Handlers go in before the lock exists so an early signal cannot leak it.
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    # Closing the launching terminal sends SIGHUP. Dying on it would leave a
    # dead pid in the lock, which the weekly wrapper clears as stale and then
    # runs mid-rebuild, so the holder ignores it; only release/SIGTERM/SIGINT stop it.
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_dir.mkdir()
    except FileExistsError:
        # Only a pid file naming a dead process is stale. A lock with no
        # readable pid may be a live writer between its mkdir and pid write
        # (the wrapper treats that as held too), so refuse.
        pid, owner, alive = _holder(lock_dir)
        if pid is None or alive:
            print(f"lock held by pid {pid} (owner {owner})", file=sys.stderr)
            return 1
        print(f"clearing stale lock (pid {pid})", file=sys.stderr)
        shutil.rmtree(lock_dir, ignore_errors=True)
        try:
            lock_dir.mkdir()
        except FileExistsError:
            print("lost race for the lock", file=sys.stderr)
            return 1

    try:
        _write_atomic(lock_dir / "owner", OWNER + "\n")
        _write_atomic(lock_dir / "pid", str(os.getpid()) + "\n")
        print(f"holding {lock_dir} as pid {os.getpid()}", flush=True)
        while not stop.wait(1.0):
            pass
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)
    return 0


def cmd_release(lock_dir):
    pid, owner, alive = _holder(lock_dir)
    if owner != OWNER:
        print(f"refusing: lock owner is {owner!r}, not {OWNER!r}", file=sys.stderr)
        return 1
    if not alive:
        print(f"holder pid {pid} is not alive; nothing to signal", file=sys.stderr)
        return 1
    os.kill(pid, signal.SIGTERM)
    print(f"sent SIGTERM to {pid}")
    return 0


def cmd_status(lock_dir):
    pid, owner, alive = _holder(lock_dir)
    print(f"pid={pid} owner={owner} alive={alive}")
    return 0 if (owner == OWNER and alive) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["hold", "release", "status"])
    ap.add_argument("--lock-dir", type=Path, default=DEFAULT_LOCK_DIR)
    args = ap.parse_args(argv)
    return {"hold": cmd_hold, "release": cmd_release, "status": cmd_status}[args.command](args.lock_dir)


if __name__ == "__main__":
    sys.exit(main())
