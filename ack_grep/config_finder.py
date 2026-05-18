"""Locates configuration files (.ackrc)."""

from __future__ import annotations

import os

import ack_grep


def _check_for_ackrc(*path_parts: str) -> list[str]:
    """Check a directory for .ackrc or _ackrc files."""
    if not path_parts or path_parts[0] is None:
        return []

    directory = os.path.join(*path_parts) if len(path_parts) > 1 else path_parts[0]
    candidates = [
        os.path.join(directory, ".ackrc"),
        os.path.join(directory, "_ackrc"),
    ]
    found = [f for f in candidates if os.path.isfile(f)]

    if len(found) > 1:
        ack_grep.die(
            f"{directory} contains both .ackrc and _ackrc. Please remove one of those files."
        )

    return found


def _remove_redundancies(configs: list[dict]) -> list[dict]:
    """Remove duplicate config files."""
    seen: set[str] = set()
    unique: list[dict] = []

    for config in configs:
        path = config["path"]
        if os.path.exists(path):
            key = os.path.realpath(path)
            if not ack_grep.is_windows:
                try:
                    stat = os.stat(key)
                    key = f"{stat.st_dev}:{stat.st_ino}"
                except OSError:
                    pass
        else:
            key = path

        if key not in seen:
            seen.add(key)
            unique.append(config)

    return unique


def find_config_files() -> list[dict]:
    """Locate all config files."""
    config_files: list[dict] = []

    if ack_grep.is_windows:
        appdata = os.environ.get("APPDATA", "")
        common_appdata = os.environ.get("PROGRAMDATA", "")
        if common_appdata:
            config_files.append({"path": os.path.join(common_appdata, "ackrc")})
        if appdata:
            config_files.append({"path": os.path.join(appdata, "ackrc")})
    else:
        config_files.append({"path": "/etc/ackrc"})

    ackrc_env = os.environ.get("ACKRC")
    if ackrc_env and os.path.isfile(ackrc_env):
        config_files.append({"path": ackrc_env})
    else:
        home = os.environ.get("HOME")
        if home:
            for f in _check_for_ackrc(home):
                config_files.append({"path": f})

    cwd = os.getcwd()
    parts = []
    head = cwd
    while True:
        head, tail = os.path.split(head)
        if tail:
            parts.insert(0, tail)
        else:
            if head:
                parts.insert(0, head)
            break

    for i in range(len(parts), 0, -1):
        dirpath = os.path.join(*parts[:i]) if i > 1 else parts[0]
        found = _check_for_ackrc(dirpath)
        if found:
            config_files.append({"path": found[0], "project": True})
            break

    return _remove_redundancies(config_files)
