"""Compatibility alias for :mod:`memento.smart_store`."""

from importlib import import_module as _import_module
from sys import modules as _modules

_modules[__name__] = _import_module("memento.smart_store")
