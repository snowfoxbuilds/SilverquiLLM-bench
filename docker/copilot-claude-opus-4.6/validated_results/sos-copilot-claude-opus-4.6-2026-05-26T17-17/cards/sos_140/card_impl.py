"""Card implementation for Ambitious Augmenter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class AmbitiousAugmenter(Creature):
    """Ambitious Augmenter — {G} — Creature — Turtle Wizard — 1/1.

    Increment (Whenever you cast a spell, if the amount of mana you spent is
    greater than this creature's power or toughness, put a +1/+1 counter on
    this creature.)
    When this creature dies, if it had one or more counters on it, create a 0/0
    green and blue Fractal creature token, then put this creature's counters on
    that token.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ambitious Augmenter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Turtle", "Wizard"})
        kwargs.setdefault(
            "rules_text",
            "Increment (Whenever you cast a spell, if the amount of mana you "
            "spent is greater than this creature's power or toughness, put a "
            "+1/+1 counter on this creature.)\n"
            "When this creature dies, if it had one or more counters on it, "
            "create a 0/0 green and blue Fractal creature token, then put this "
            "creature's counters on that token.",
        )
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", spell: Any = None) -> None:
        """Increment: put +1/+1 counter if mana spent > power or toughness."""
        if spell is None:
            return
        mana_spent = getattr(spell, "mana_spent", 0)
        current_power = self.get_power()
        current_toughness = self.get_toughness()
        if mana_spent > current_power or mana_spent > current_toughness:
            self.plus_one_counters += 1

    def on_death(self, game: "GameState") -> None:
        """Dies trigger: create Fractal token with this creature's counters."""
        counters = getattr(self, "plus_one_counters", 0)
        if counters <= 0:
            return

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
        fractal.plus_one_counters = counters

        game.get_battlefield(controller).add(fractal)
