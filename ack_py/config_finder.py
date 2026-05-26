"""Locate ackrc configuration files.

Ported from lib/App/Ack/ConfigFinder.pm.
"""

from __future__ import annotations

import os
import sys


def find_config_files() -> list[dict[str, str | bool]]:
    """Locate config files in order: global, user, project."""
    config_files: list[dict[str, str | bool]] = []

    # Global ackrc
    if sys.platform == "win32":
        for var in ("APPDATA", "COMMONAPPDATA"):
            folder = os.environ.get(var, "")
            if folder:
                config_files.append({"path": os.path.join(folder, "ackrc")})
    else:
        config_files.append({"path": "/etc/ackrc"})

    # User ackrc (ACKRC env or ~/.ackrc)
    ackrc_env = os.environ.get("ACKRC", "")
    if ackrc_env and os.path.isfile(ackrc_env):
        config_files.append({"path": ackrc_env})
    else:
        home = os.environ.get("HOME", "")
        if home:
            for name in (".ackrc", "_ackrc"):
                path = os.path.join(home, name)
                if os.path.isfile(path):
                    config_files.append({"path": path})
                    break

    # Project ackrc — walk up from cwd
    try:
        cwd = os.getcwd()
    except OSError:
        return _remove_redundancies(config_files)

    parts = cwd.split(os.sep)
    while parts:
        candidate_dir = os.sep.join(parts) or os.sep
        found = _check_for_ackrc(candidate_dir)
        if found:
            config_files.append({"path": found, "project": True})
            break
        parts.pop()

    return _remove_redundancies(config_files)


def _check_for_ackrc(directory: str) -> str | None:
    """Return the ackrc path inside directory, or None."""
    candidates = []
    for name in (".ackrc", "_ackrc"):
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            candidates.append(path)

    if len(candidates) > 1:
        raise SystemExit(f"ack: {directory} contains both .ackrc and _ackrc. Please remove one of those files.")

    return candidates[0] if candidates else None


def _remove_redundancies(configs: list[dict[str, str | bool]]) -> list[dict[str, str | bool]]:
    """Remove duplicate config file entries."""
    seen: set[str] = set()
    result: list[dict[str, str | bool]] = []
    for cfg in configs:
        path = str(cfg["path"])
        try:
            key = os.path.realpath(path) if os.path.exists(path) else path
        except OSError:
            key = path

        if sys.platform != "win32" and os.path.exists(key):
            try:
                stat = os.stat(key)
                key = f"{stat.st_dev}:{stat.st_ino}"
            except OSError:
                pass

        if key not in seen:
            seen.add(key)
            result.append(cfg)
    return result
