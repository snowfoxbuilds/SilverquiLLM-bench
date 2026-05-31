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
        """Register the casualty trigger for instant/sorcery spells cast by controller."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Mutable cell: condition() writes the spell card here so that effect()
        # can find the matching StackObject when it resolves.
        _pending: dict[str, Any] = {"card": None}

        def _condition(game: Any, event: Any) -> bool:
            card = getattr(event, "card", None)
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            ctrl = getattr(source, "controller", None)
            event_ctrl = getattr(event, "controller", None)
            if event_ctrl is not ctrl:
                return False
            _pending["card"] = card
            return True

        def _effect(game: "GameState") -> None:
            original_card = _pending["card"]
            if original_card is None:
                return

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Gather sacrifice candidates: creatures with power >= 1.
            bf = game.get_battlefield(ctrl)
            candidates = [
                c
                for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]

            if not candidates:
                return

            # "You may" — offer the sacrifice.
            try:
                wants_to = ctrl.choose_yes_no(
                    "casualty 1: sacrifice a creature with power 1 or greater?"
                )
            except Exception:
                return

            if not wants_to:
                return

            # Choose which creature to sacrifice.
            try:
                chosen = ctrl.choose_card(
                    candidates,
                    "casualty 1: choose a creature with power 1 or greater to sacrifice",
                )
            except Exception:
                return

            if chosen is None:
                return

            # Perform the sacrifice.
            from engine.game import sacrifice
            sacrifice(game, ctrl, chosen)

            # Locate the original spell's StackObject (still on the stack).
            original_stack_obj = None
            for obj in game.stack._items:
                if obj.source is original_card:
                    original_stack_obj = obj
                    break

            if original_stack_obj is None:
                return

            # Create a copy of the spell and push it on top of the stack.
            from engine.stack import copy_spell
            copy_obj = copy_spell(game, original_stack_obj, ctrl, new_targets=None)
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

