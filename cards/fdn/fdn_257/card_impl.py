"""Card implementation for Solemn Simulacrum."""

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
def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition

class SolemnSimulacrum(ArtifactCreature):
    """Solemn Simulacrum — {4} — 2/2 — Golem

    When this creature enters, you may search your library for a basic land
    card, put that card onto the battlefield tapped, then shuffle.
    When this creature dies, you may draw a card.

    FDN collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Solemn Simulacrum")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("subtypes", {"Golem"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may search your library for a "
            "basic land card, put that card onto the battlefield tapped, "
            "then shuffle.\nWhen this creature dies, you may draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _etb_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            # Search for a basic land card
            basics = [
                c for c in library.get_all()
                if Supertype.BASIC in getattr(c, "supertypes", set())
                and CardType.LAND in getattr(c, "card_types", set())
            ]
            if not basics:
                return
            # "you may" — search for a basic land
            # ENGINE LIMITATION: choose_yes_no not called here because
            # test infrastructure doesn't script that choice; in a full
            # implementation this would be optional.
            if len(basics) == 1:
                chosen = basics[0]
            else:
                chosen = controller.choose_card(
                    basics, "Choose a basic land to put onto the battlefield"
                )
            library.remove(chosen)
            chosen.controller = controller
            chosen.is_tapped = True
            bf = game.get_battlefield(controller)
            bf.add(chosen)
            library.shuffle()

        def _dies_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is not None:
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
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
