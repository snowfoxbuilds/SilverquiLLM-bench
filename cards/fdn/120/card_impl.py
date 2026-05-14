"""Card implementation for Fiendish Panda."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _self_dies_condition(source: Any):
    """Return a condition callable that matches only when *source* dies."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("creature") is source

    return _condition
def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class FiendishPanda(Creature):
    """Fiendish Panda — {2}{W}{B} — 3/2 — Bear Demon

    Whenever you gain life, put a +1/+1 counter on this creature.
    When this creature dies, return another target non-Bear creature card
    with mana value less than or equal to this creature's power from your
    graveyard to the battlefield.

    FDN collector number 120.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fiendish Panda")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Bear", "Demon"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever you gain life, put a +1/+1 counter on this "
            "creature.\nWhen this creature dies, return another target "
            "non-Bear creature card with mana value less than or equal "
            "to this creature's power from your graveyard to the "
            "battlefield.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import add_counter
        from engine.zones import move_to_zone

        source = self

        def _lifegain_condition(game: Any, data: dict) -> bool:
            # ENGINE LIMITATION: GAINS_LIFE event may not carry enough
            # data to identify the gaining player. Simplified: check
            # if the gaining player is the controller.
            player = data.get("player")
            controller = getattr(source, "controller", None)
            return player is controller

        def _lifegain_effect(game: GameState) -> None:
            if _is_on_battlefield(game, source):
                add_counter(game, source, "+1/+1", 1)

        def _dies_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            power = getattr(source, "power", getattr(source, "base_power", 3))
            graveyard = controller.zones[Zone.GRAVEYARD]
            candidates = []
            for obj in graveyard.get_all():
                if obj is source:
                    continue
                card_types = getattr(obj, "card_types", set())
                if CardType.CREATURE not in card_types:
                    continue
                subtypes = getattr(obj, "subtypes", set())
                if "Bear" in subtypes:
                    continue
                mana_cost = getattr(obj, "mana_cost", None)
                if mana_cost is not None and mana_cost.cmc <= power:
                    candidates.append(obj)
            if candidates:
                target = candidates[0]
                target.controller = controller
                move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.GAINS_LIFE,
            condition=_lifegain_condition,
            effect=_lifegain_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))
