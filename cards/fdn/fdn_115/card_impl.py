"""Card implementation for Alesha, Who Laughs at Fate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AleshaWhoLaughsAtFate(Creature):
    """Alesha, Who Laughs at Fate — {1}{B}{R} — 2/2 — Legendary Human Warrior.

    First strike
    Whenever Alesha attacks, put a +1/+1 counter on it.
    Raid — At the beginning of your end step, if you attacked this turn,
    return target creature card with mana value less than or equal to
    Alesha's power from your graveyard to the battlefield.

    FDN collector number 115.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Alesha, Who Laughs at Fate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Warrior"})
        kwargs.setdefault("supertypes", {"Legendary"})
        kwargs.setdefault("keywords", Keyword.FIRST_STRIKE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "First strike\n"
            "Whenever Alesha attacks, put a +1/+1 counter on it.\n"
            "Raid — At the beginning of your end step, if you attacked "
            "this turn, return target creature card with mana value less "
            "than or equal to Alesha's power from your graveyard to the "
            "battlefield.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger and Raid end-step trigger."""
        from engine.game import add_counter
        from engine.triggers import EventType, TriggerRegistration
        from engine.zones import move_to_zone
        from engine.types import CardType

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- Attack trigger: +1/+1 counter ---
        def _attack_condition(game: Any, data: dict) -> bool:
            return data.get("creature") is source

        def _attack_effect(game: "GameState") -> None:
            add_counter(game, source, "+1/+1")
            source._original_plus_one_counters = source.plus_one_counters  # type: ignore[attr-defined]

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ATTACKS,
            condition=_attack_condition,
            effect=_attack_effect,
            source=self,
            controller=controller,
        ))

        # --- Raid end-step trigger: graveyard recursion ---
        def _raid_condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            attacked = getattr(game, "attacked_this_turn", False)
            if not attacked:
                attacked = getattr(ctrl, "attacked_this_turn", False)
            return attacked

        def _raid_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            power = getattr(source, "power", getattr(source, "base_power", 2))
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                c for c in graveyard.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "mana_cost", None) is not None
                and c.mana_cost.cmc <= power
            ]
            if not candidates:
                return
            try:
                chosen = ctrl.choose_card(
                    candidates,
                    "creature card to return from graveyard",
                )
            except Exception:
                chosen = candidates[0]
            if chosen is None:
                return
            chosen.controller = ctrl
            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.END_STEP,
            condition=_raid_condition,
            effect=_raid_effect,
            source=self,
            controller=controller,
        ))
