"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Creature — Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast
    that spell, you may sacrifice a creature with power 1 or greater. When
    you do, copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
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

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            spell_card = getattr(event, "card", None)
            card_types = getattr(spell_card, "card_types", set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            source._casualty_pending = getattr(event, "spell", None)
            return True

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            stack_obj = getattr(source, "_casualty_pending", None)
            source._casualty_pending = None
            if ctrl is None or stack_obj is None:
                return
            # The spell must still be on the stack to be copied.
            if stack_obj not in game.stack._items:  # noqa: SLF001
                return
            candidates = [
                c
                for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return
            # One prompt: the answer is the creature to sacrifice (None declines).
            try:
                chosen = ctrl.choose_card(
                    candidates, "casualty 1 — sacrifice a creature with power 1 or greater?"
                )
            except Exception:
                chosen = None
            if chosen is None or chosen not in candidates:
                return

            from engine.game import sacrifice

            sacrifice(game, ctrl, chosen)
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
