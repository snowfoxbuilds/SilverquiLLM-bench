"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


def _on_battlefield(game: "GameState", obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.

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
        """Grant casualty 1 to instant/sorcery spells the controller casts."""
        from engine.triggers import TriggerRegistration
        from engine.events import SpellCastTriggeredEvent
        from engine.stack import copy_spell

        source = self
        controller = getattr(self, "controller", None) or game.active_player
        source._casualty_pending: list[Any] = []

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl:
                return False
            if not _on_battlefield(game, source):
                return False
            spell_obj = getattr(event, "spell", None)
            spell_card = getattr(spell_obj, "source", None) if spell_obj else None
            spell_card = spell_card or getattr(event, "card", None)
            if spell_card is None:
                return False
            if not (getattr(spell_card, "card_types", set()) & _SPELL_TYPES):
                return False
            # Stash the triggering spell's StackObject for the effect to copy.
            source._casualty_pending.append(spell_obj)
            return True

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            spell_obj = source._casualty_pending.pop() if source._casualty_pending else None
            if ctrl is None or spell_obj is None:
                return
            # Casualty 1: may sacrifice a creature with power 1 or greater.
            valid = [
                c for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not valid:
                return
            chosen = ctrl.choose_card(
                valid, "casualty 1: sacrifice a creature with power 1+ (or decline)"
            )
            if chosen is None or chosen not in valid:
                return
            from engine.game import sacrifice
            sacrifice(game, ctrl, chosen)
            # When you do, copy the spell (same targets; copy is not "cast").
            copy_obj = copy_spell(game, spell_obj, ctrl)
            game.stack.push(copy_obj)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
