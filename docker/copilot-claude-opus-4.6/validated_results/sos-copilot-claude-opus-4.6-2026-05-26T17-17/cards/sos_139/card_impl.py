"""Card implementation for Additive Evolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Enchantment
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class AdditiveEvolution(Enchantment):
    """Additive Evolution — {3}{G}{G} — Enchantment.

    When this enchantment enters, create a 0/0 green and blue Fractal creature
    token. Put three +1/+1 counters on it.
    At the beginning of combat on your turn, put a +1/+1 counter on target
    creature you control. It gains vigilance until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Additive Evolution")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault(
            "rules_text",
            "When this enchantment enters, create a 0/0 green and blue Fractal "
            "creature token. Put three +1/+1 counters on it.\n"
            "At the beginning of combat on your turn, put a +1/+1 counter on "
            "target creature you control. It gains vigilance until end of turn.",
        )
        super().__init__(**kwargs)

    def on_enter_battlefield(self, game: "GameState") -> None:
        """ETB: Create a 0/0 Fractal token with three +1/+1 counters."""
        controller = self.controller
        if controller is None:
            return

        fractal = Creature(
            name="Fractal",
            owner=controller,
            controller=controller,
            base_power=0,
            base_toughness=0,
        )
        fractal.card_types = {CardType.CREATURE}
        fractal.subtypes = {"Fractal"}
        fractal.is_token = True
        fractal.plus_one_counters = 3

        game.get_battlefield(controller).add(fractal)

    def on_combat_begin(self, game: "GameState") -> None:
        """Beginning of combat: +1/+1 counter and vigilance on target creature."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target = chosen[0]
        target.plus_one_counters = getattr(target, "plus_one_counters", 0) + 1
        target.keywords = getattr(target, "keywords", Keyword(0)) | Keyword.VIGILANCE
