"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance.  Each instant and sorcery spell you cast has
    casualty 1 (as you cast it, you may sacrifice a creature with power 1
    or greater; when you do, copy the spell).

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1.",
        )
        super().__init__(**kwargs)
        # LIFO queue of spells awaiting their casualty trigger resolution.
        self._casualty_pending: list[Any] = []

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            if not _is_on_battlefield(g, source):
                return False
            spell = getattr(event, "spell", None)
            if spell is None or spell is source:
                return False
            controller = source.controller
            if controller is None:
                return False
            if getattr(spell, "controller", None) is not controller:
                return False
            if not _is_instant_or_sorcery(spell):
                return False
            source._casualty_pending.append(spell)
            return True

        def _effect(g: "GameState") -> None:
            source._resolve_casualty(g)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _resolve_casualty(self, game: "GameState") -> None:
        """Offer casualty 1 for the most recently cast pending spell."""
        from engine.game import sacrifice
        from engine.stack import copy_spell

        if not self._casualty_pending:
            return
        spell = self._casualty_pending.pop()

        controller = self.controller
        if controller is None:
            return

        candidates = [
            c
            for c in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
            and getattr(c, "power", 0) >= 1
        ]
        if not candidates:
            return

        if not controller.choose_yes_no(
            "Casualty 1 — sacrifice a creature with power 1 or greater?"
        ):
            return

        chosen = controller.choose_card(candidates, "creature to sacrifice (casualty)")
        if chosen is None or chosen not in candidates:
            return

        sacrifice(game, controller, chosen)

        # Copy the spell: find its StackObject (still below this trigger).
        for stack_obj in game.stack.objects():
            if stack_obj.source is spell:
                game.stack.push(copy_spell(game, stack_obj, controller))
                break
