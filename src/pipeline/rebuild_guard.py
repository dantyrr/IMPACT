"""Safety helpers shared by the long-running rebuild scripts."""
import os
import shutil
import subprocess
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCK_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "rebuild_lock.py")
GB = 1e9


def free_gb(path: str) -> float:
    return shutil.disk_usage(path).free / GB


def rebuild_lock_held() -> bool:
    """True iff `rebuild_lock.py status` reports a live `rebuild` holder (exit 0)."""
    r = subprocess.run([sys.executable, LOCK_SCRIPT, "status"], capture_output=True)
    return r.returncode == 0


def _checkpoint(conn) -> None:
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
