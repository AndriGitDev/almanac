"""Almanac environment variable lookup."""

import os


def get_env(suffix: str, default: str | None = None) -> str | None:
    """Read an ``ALMANAC_*`` environment variable."""

    return os.environ.get(f"ALMANAC_{suffix}", default)
