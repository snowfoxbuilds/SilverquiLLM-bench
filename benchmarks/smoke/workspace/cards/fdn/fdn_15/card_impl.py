"""Card implementation for Hare Apparent (FDN #15)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class HareApparentAbility1:
    text = 'When this creature enters, create a number of 1/1 white Rabbit creature tokens equal to the number of other creatures you control named Hare Apparent.'


class HareApparentAbility2:
    text = 'A deck can have any number of cards named Hare Apparent.'


# endregion Printed abilities


class HareApparent(Creature):
    """Hare Apparent — {1}{W} — 2/2 — Rabbit Noble.

    When this creature enters, create a number of 1/1 white Rabbit creature
    tokens equal to the number of other creatures you control named Hare
    Apparent.

    A deck can have any number of cards named Hare Apparent.

    FDN collector number 15.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hare Apparent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Rabbit", "Noble"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, create a number of 1/1 white Rabbit "
            "creature tokens equal to the number of other creatures you "
            "control named Hare Apparent.\n"
            "A deck can have any number of cards named Hare Apparent.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, HareApparentAbility1, self._enters)

    def _enters(self, game: "GameState", controller: Any) -> None:
        """One 1/1 white Rabbit per *other* Hare Apparent you control.

        The ``obj is not self`` guard keeps the "other" semantics: the
        trigger resolves with this creature already on the battlefield.
        """
        from engine.game import create_token

        if controller is None:
            return

        count = sum(
            1
            for obj in game.get_battlefield(controller).get_all()
            if obj is not self
            and CardType.CREATURE in getattr(obj, "card_types", set())
            and getattr(obj, "name", None) == "Hare Apparent"
        )

        from cards.fdn.tokens import make_creature_token

        for _ in range(count):
            # Route through the shared factory so the 1/1 white Rabbit's
            # identity (grpId 94160) has its single definition there.
            token = make_creature_token("Rabbit", {"Rabbit"}, [Color.WHITE], 1, 1)
            create_token(game, controller, token)
