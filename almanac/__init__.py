"""Almanac's public Python namespace.

The implementation remains in ``memento`` during the compatibility migration.
Submodules are exact aliases, so both import paths share caches and state.
"""

from memento import __version__

__all__ = ["__version__"]
