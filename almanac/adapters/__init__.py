"""Almanac transcript adapters backed by the legacy package."""

import memento.adapters as _legacy


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_legacy)))
