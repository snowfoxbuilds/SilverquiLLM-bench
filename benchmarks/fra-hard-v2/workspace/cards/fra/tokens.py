"""Predefined classes for the tokens FRA keyword actions create.

Tokens have no Card Spec, so the token and its abilities are predefined here
(see ADR-017), behavior-free: a token created by a keyword action stands for
its class here, and each of its abilities for the matching ability class.
"""

from engine.card import Planeswalker
from engine.types import Color


class JaceTokenAbility1:
    text = "[−1]: Surveil 1."


class JaceTokenAbility2:
    text = "[−3]: Draw a card."


class JaceToken(Planeswalker):
    """The blue Jace planeswalker token "empower Jace" creates (rule 701.71a)."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Jace',
            'subtypes': {'Jace'},
            'starting_loyalty': 0,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
        self.colors = {Color.BLUE}
