"""Shared helpers for reading/writing the project's .env file.

Kept dependency-free (stdlib only) so it can be used both by the running
application (src/telegram_bot.py) and by the standalone first-run setup tool
(src/setup.py), which runs before third-party packages are installed.
"""
import os
from pathlib import Path


def set_env_var(env_file: Path, key: str, value: str) -> None:
    """Atomically replace-or-append ``KEY=value`` in ``env_file``.

    Preserves all other lines, creates the file if it does not exist, and
    writes durably (flush + fsync + atomic rename) so a crash mid-write cannot
    leave a truncated .env behind. Raises on failure.
    """
    lines = []
    found = False
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")

    # Write to a temp file next to .env, then rename over it (atomic on POSIX
    # and Windows). fsync forces the bytes to disk before the rename.
    tmp_file = env_file.parent / (env_file.name + ".tmp")
    try:
        with open(tmp_file, "w") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        tmp_file.replace(env_file)
    except Exception:
        tmp_file.unlink(missing_ok=True)
        raise
