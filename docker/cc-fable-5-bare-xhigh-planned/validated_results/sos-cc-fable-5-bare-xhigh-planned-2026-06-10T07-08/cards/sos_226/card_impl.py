"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast
    that spell, you may sacrifice a creature with power 1 or greater. When
    you do, copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1. (As you cast that spell, you may sacrifice a "
            "creature with power 1 or greater. When you do, copy the spell "
            "and you may choose new targets for the copy.)",
        )
        super().__init__(**kwargs)
        # Pending StackObjects of spells whose casualty is being offered
        # (LIFO — matches trigger resolution order off the stack).
        self._pending_spells: list[Any] = []

    def register_triggers(self, game: GameState) -> None:
        """Casualty 1 on your instant/sorcery spells while on the battlefield."""
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            if not (_SPELL_TYPES & getattr(card, "card_types", set())):
                return False
            source._pending_spells.append(getattr(event, "spell", None))
            return True

        def _effect(game: GameState) -> None:
            ctrl = getattr(source, "controller", None)
            stack_obj = source._pending_spells.pop() if source._pending_spells else None
            if ctrl is None or stack_obj is None:
                return
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
                "Casualty 1 — sacrifice a creature with power 1 or greater? "
                "(None to decline)",
            )
            if chosen is None or chosen not in candidates:
                return
            if getattr(chosen, "power", 0) < 1:
                return
            sacrifice(game, ctrl, chosen)
            # Copy works even if the original has left the stack (rule 707.10c).
            copy_obj = copy_spell(game, stack_obj, ctrl)
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
