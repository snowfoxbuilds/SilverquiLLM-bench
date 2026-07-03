"""Card implementation for Cuboid Colony."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class CuboidColony(Creature):
    """Cuboid Colony — {G}{U} — 1/1 Creature — Insect.

    Flash
    Flying, trample
    Increment (Whenever you cast a spell, if the amount of mana you spent is
    greater than this creature's power or toughness, put a +1/+1 counter on
    this creature.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cuboid Colony")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{U}"))
        kwargs.setdefault("subtypes", {"Insect"})
        kwargs.setdefault(
            "keywords",
            Keyword.FLASH | Keyword.FLYING | Keyword.TRAMPLE,
        )
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register increment trigger."""
        source = self
        controller = self.controller

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            if event.player is not source.controller:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            # Don't trigger on self being cast
            if spell is source:
                return False
            mana_spent = getattr(event, "mana_spent", 0)
            if mana_spent == 0:
                mana_cost = getattr(spell, "mana_cost", None)
                if mana_cost is not None:
                    mana_spent = mana_cost.cmc
            # Greater than power OR toughness
            return mana_spent > source.power or mana_spent > source.toughness

        def _effect(game: "GameState") -> None:
            source.plus_one_counters += 1
            source._base_plus_one_counters = source.plus_one_counters

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
