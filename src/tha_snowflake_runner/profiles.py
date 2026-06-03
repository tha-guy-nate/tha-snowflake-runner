from __future__ import annotations

import os
from typing import Any

from tha_snowflake_runner.errors import SnowflakeError

try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


def _detect_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".toml":
        return "toml"
    if ext in (".ini", ".cfg"):
        return "ini"
    if ext == ".json":
        return "json"
    raise SnowflakeError(
        f"Unsupported connections_file format: {ext!r}. Use .toml, .ini, .cfg, or .json"
    )


def _load_all_profiles(path: str) -> dict[str, dict[str, Any]]:
    fmt = _detect_format(path)
    profiles: dict[str, dict[str, Any]] = {}
    if fmt == "toml":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            if k == "connections":
                profiles.update({ck: cv for ck, cv in v.items() if isinstance(cv, dict)})
            else:
                profiles[k] = v
    elif fmt == "ini":
        import configparser
        with open(path) as f:
            content = f.read()
        cp = configparser.ConfigParser()
        cp.read_string(content)
        for section in cp.sections():
            profiles[section] = dict(cp[section])
    elif fmt == "json":
        import json
        with open(path) as f:
            data = json.load(f)
        connections = data.get("connections")
        if isinstance(connections, dict):
            profiles.update({k: v for k, v in connections.items() if isinstance(v, dict)})
        else:
            profiles.update({k: v for k, v in data.items() if isinstance(v, dict)})
    return profiles


def list_profiles(path: str) -> list[str]:
    """Return available profile names from a connections file (.toml, .ini/.cfg, .json)."""
    expanded = os.path.expanduser(path)
    if not os.path.exists(expanded):
        raise SnowflakeError(f"connections_file not found: {expanded}")
    return list(_load_all_profiles(expanded).keys())
