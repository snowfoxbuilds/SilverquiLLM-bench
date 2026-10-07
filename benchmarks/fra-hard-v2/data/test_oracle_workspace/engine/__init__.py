"""The Known-Best engine package.

The engine's player is the abstract :class:`Player`; the players that answer
tests' queries belong to the Test Interface and ``test_utils``.
"""

from engine.player import Player

__all__ = ["Player"]
