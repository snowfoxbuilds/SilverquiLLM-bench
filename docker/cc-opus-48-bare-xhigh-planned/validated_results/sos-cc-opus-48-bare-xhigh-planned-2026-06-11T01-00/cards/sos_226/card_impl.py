"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}


def _on_battlefield(game: "GameState", obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance
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
            "casualty 1. (As you cast that spell, you may sacrifice a creature "
            "with power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not source.controller:
                return False
            card = getattr(event, "card", None)
            if card is None or not (getattr(card, "card_types", set()) & _INSTANT_SORCERY):
                return False
            if not _on_battlefield(game, source):
                return False
            source._casualty_spell = getattr(event, "spell", None)
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = source.controller
            spell = getattr(source, "_casualty_spell", None)
            if ctrl is None or spell is None:
                return
            # Casualty 1: optionally sacrifice a creature with power >= 1.
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
                "Casualty 1: sacrifice a creature with power 1 or greater "
                "(or decline)",
            )
            if chosen is None or chosen not in candidates:
                return
            if getattr(chosen, "power", 0) < 1:
                return
            sacrifice(game, ctrl, chosen)
            # Copy the spell (new targets may be chosen; keeping the same
            # targets is a legal choice and is the deterministic default).
            copy_obj = copy_spell(game, spell, ctrl)
            game.stack.push(copy_obj)

        from engine.events import SpellCastTriggeredEvent

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
