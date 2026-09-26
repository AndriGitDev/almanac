"""Compatibility alias for :mod:`almanac.archive`."""

if __name__ == "__main__":
    from runpy import run_module

    run_module("almanac.archive", run_name="__main__", alter_sys=True)
else:
    from importlib import import_module as _import_module
    from sys import modules as _modules

    _modules[__name__] = _import_module("almanac.archive")
