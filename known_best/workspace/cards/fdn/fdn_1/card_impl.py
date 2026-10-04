"""Card implementation for Sire of Seven Deaths."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SireOfSevenDeathsAbility1:
    text = 'First strike'


class SireOfSevenDeathsAbility2:
    text = 'vigilance'


class SireOfSevenDeathsAbility3:
    text = 'Menace'


class SireOfSevenDeathsAbility4:
    text = 'trample'


class SireOfSevenDeathsAbility5:
    text = 'Reach'


class SireOfSevenDeathsAbility6:
    text = 'lifelink'


class SireOfSevenDeathsAbility7:
    text = 'Ward—Pay 7 life.'


# endregion Printed abilities


class SireOfSevenDeaths(Creature):
    """Sire of Seven Deaths — {7} — 7/7 — Eldrazi.

    First strike, vigilance
    Menace, trample
    Reach, lifelink
    Ward—Pay 7 life.

    FDN collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sire of Seven Deaths")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("subtypes", {"Eldrazi"})
        kwargs.setdefault(
            "keywords",
            (
                Keyword.FIRST_STRIKE
                | Keyword.VIGILANCE
                | Keyword.MENACE
                | Keyword.TRAMPLE
                | Keyword.REACH
                | Keyword.LIFELINK
                | Keyword.WARD
            ),
        )
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "First strike, vigilance\nMenace, trample\nReach, lifelink\n"
            "Ward\u2014Pay 7 life.",
        )
        super().__init__(**kwargs)
        # ENGINE LIMITATION: Ward cost (pay 7 life) is not enforced by the
        # engine. The engine recognizes the Ward keyword but does not
        # currently support custom ward costs beyond generic mana.
        self.ward_cost = 7  # life payment
