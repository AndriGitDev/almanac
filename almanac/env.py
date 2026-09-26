"""Environment variable lookup with Almanac names and Memento fallbacks."""

import os


def get_env(suffix: str, default: str | None = None) -> str | None:
    """Prefer ``ALMANAC_*`` and accept ``MEMENTO_*`` for existing installs."""

    return os.environ.get(f"ALMANAC_{suffix}", os.environ.get(f"MEMENTO_{suffix}", default))
