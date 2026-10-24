"""Tests for scripts/rebuild_lock.py. Always uses a tmp --lock-dir."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rebuild_lock.py"

# Lock-acquire stanza replicated from scripts/weekly_auto_update.sh:122-130,
# with log() replaced by echo so the branch taken is observable.
WRAPPER_STANZA = r'''
LOCK_DIR="$1"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    if [ -f "$LOCK_DIR/pid" ] && ! /bin/kill -0 "$(cat "$LOCK_DIR/pid")" 2>/dev/null; then
        echo "clearing stale lock from pid $(cat "$LOCK_DIR/pid")"
        rm -rf "$LOCK_DIR" && mkdir "$LOCK_DIR" 2>/dev/null
    else
        echo "lock held - exiting"
        exit 0
    fi
fi
echo "acquired"
'''


def run(*args, lock_dir):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--lock-dir", str(lock_dir)],
        capture_output=True, text=True, timeout=30,
    )


def wait_for(path, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if path.exists() and path.read_text().strip():
            return
        time.sleep(0.05)
    raise AssertionError(f"{path} never appeared")


@pytest.fixture
def lock_dir(tmp_path):
    return tmp_path / "weekly.lock"


@pytest.fixture
def holders():
    procs = []
    yield procs
    for p in procs:
        if p.poll() is None:
            p.kill()
        p.wait()


def start_hold(lock_dir, holders):
    p = subprocess.Popen(
        [sys.executable, str(SCRIPT), "hold", "--lock-dir", str(lock_dir)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    holders.append(p)
    wait_for(lock_dir / "owner")
    wait_for(lock_dir / "pid")
    return p


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_hold_writes_live_pid(lock_dir, holders):
    p = start_hold(lock_dir, holders)
    assert int((lock_dir / "pid").read_text()) == p.pid
    assert (lock_dir / "owner").read_text().strip() == "rebuild"
    assert run("status", lock_dir=lock_dir).returncode == 0
    p.send_signal(signal.SIGTERM)
    assert p.wait(timeout=10) == 0
    assert not lock_dir.exists()
    assert run("status", lock_dir=lock_dir).returncode == 1


def test_sigint_also_cleans_up(lock_dir, holders):
    p = start_hold(lock_dir, holders)
    p.send_signal(signal.SIGINT)
    assert p.wait(timeout=10) == 0
    assert not lock_dir.exists()


def test_refuses_when_held_by_live_pid(lock_dir, holders):
    p = start_hold(lock_dir, holders)
    r = run("hold", lock_dir=lock_dir)
    assert r.returncode != 0
    assert int((lock_dir / "pid").read_text()) == p.pid  # untouched


def test_release_only_own_lock(lock_dir, holders):
    # A lock held by someone else (live pid, foreign owner) must not be signalled.
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    holders.append(other)
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(str(other.pid))
    (lock_dir / "owner").write_text("weekly")
    r = run("release", lock_dir=lock_dir)
    assert r.returncode != 0
    time.sleep(0.2)
    assert other.poll() is None and lock_dir.exists()
    assert run("status", lock_dir=lock_dir).returncode == 1  # not a rebuild holder

    # Our own lock is released.
    other.kill(); other.wait()
    import shutil; shutil.rmtree(lock_dir)
    p = start_hold(lock_dir, holders)
    assert run("release", lock_dir=lock_dir).returncode == 0
    assert p.wait(timeout=10) == 0
    assert not lock_dir.exists()


def test_weekly_wrapper_sees_lock_as_held(lock_dir, holders):
    def stanza():
        return subprocess.run(["bash", "-c", WRAPPER_STANZA, "_", str(lock_dir)],
                              capture_output=True, text=True, timeout=30).stdout

    p = start_hold(lock_dir, holders)
    assert "lock held" in stanza()

    # Discrimination: SIGKILL leaves the lock behind with a dead pid -> stale.
    p.kill(); p.wait()
    assert lock_dir.exists()
    out = stanza()
    assert "clearing stale lock" in out and "lock held" not in out
