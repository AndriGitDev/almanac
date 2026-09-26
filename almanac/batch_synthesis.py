"""Compatibility alias for :mod:`memento.batch_synthesis`."""

from importlib import import_module as _import_module
from sys import modules as _modules

_modules[__name__] = _import_module("memento.batch_synthesis")
