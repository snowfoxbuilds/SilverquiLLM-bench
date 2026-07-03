"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _is_on_battlefield(game: "GameState", obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

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

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not source.controller:
                return False
            spell_card = getattr(event, "card", None)
            if spell_card is None or not (
                getattr(spell_card, "card_types", set()) & _INSTANT_SORCERY
            ):
                return False
            # Stash the StackObject for the (later-resolving) effect — same
            # pattern FDN Thousand-Year Storm uses to pass the cast spell along.
            source._casualty_pending = getattr(event, "spell", None)
            return True

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            pending = getattr(source, "_casualty_pending", None)
            if ctrl is None or pending is None:
                return
            # Casualty 1: you may sacrifice a creature with power 1 or greater.
            candidates = [
                c
                for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return
            chosen = ctrl.choose_card(
                candidates,
                "Casualty 1: sacrifice a creature with power 1+ to copy the "
                "spell? (or decline)",
            )
            if chosen is None or chosen not in candidates:
                return  # declined — casualty not taken.

            from engine.game import sacrifice

            sacrifice(game, ctrl, chosen)
            # When you do, copy the spell (new targets may be chosen; we keep
            # the original targets by default). The copy goes on the stack
            # above the original and is not itself "cast" (E1 won't re-fire).
            copy_obj = copy_spell(game, pending, ctrl)
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
