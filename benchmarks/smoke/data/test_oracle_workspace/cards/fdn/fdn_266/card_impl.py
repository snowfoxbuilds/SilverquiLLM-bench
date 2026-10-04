"""Card implementation for Scoured Barrens."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ScouredBarrensAbility1:
    text = 'This land enters tapped.'


class ScouredBarrensAbility2:
    text = 'When this land enters, you gain 1 life.'


class ScouredBarrensAbility3:
    text = '{T}: Add {W} or {B}.'


# endregion Printed abilities


ScouredBarrens = make_gainlife_tapland(
    "Scoured Barrens", (ManaType.WHITE, ManaType.BLACK), 266, mana_printed=ScouredBarrensAbility3
)
