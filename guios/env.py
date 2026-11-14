"""Minimal .env loader (stdlib only) so local settings are configured once, not per terminal.

Lines are KEY=VALUE; blank lines and lines starting with # are ignored; surrounding quotes are removed.
Variables already present in the real environment always win, so hosting dashboards keep priority.
"""
import os


def load_env_file(path):
    """Load `path` into os.environ without overriding existing variables. Returns the keys it set."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    loaded = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
