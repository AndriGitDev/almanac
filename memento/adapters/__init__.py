"""Compatibility package for existing Memento adapter imports."""

from importlib import import_module as _import_module
from sys import modules as _modules

_real = _import_module("almanac.adapters")
_modules[__name__] = _real
for _name in ("claude", "opencode", "pi"):
    _modules[f"{__name__}.{_name}"] = _import_module(f"almanac.adapters.{_name}")
