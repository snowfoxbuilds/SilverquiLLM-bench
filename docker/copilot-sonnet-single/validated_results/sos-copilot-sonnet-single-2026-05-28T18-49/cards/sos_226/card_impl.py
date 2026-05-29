"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Creature — Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast
    that spell, you may sacrifice a creature with power 1 or greater. When
    you do, copy the spell and you may choose new targets for the copy.)
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
        """Register casualty trigger: when controller casts an instant/sorcery."""
        from engine.triggers import TriggerRegistration
        from engine.events import SpellCastTriggeredEvent

        source = self

        def _condition(game: Any, event: Any) -> bool:
            controller = getattr(source, "controller", None)
            on_bf = any(
                game.get_battlefield(p).contains(source)
                for p in game.players
            )
            if not on_bf:
                return False
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not controller:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            ctypes = getattr(spell, "card_types", set())
            return CardType.INSTANT in ctypes or CardType.SORCERY in ctypes

        def _casualty_effect(game: Any) -> None:
            """Offer to sacrifice a creature with power ≥ 1 to copy the spell."""
            from engine.game import sacrifice
            from engine.stack import copy_spell

            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Find creatures with power >= 1 on controller's battlefield (excluding source itself)
            bf = game.get_battlefield(controller)
            eligible = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
                and c is not source
            ]
            if not eligible:
                return

            try:
                do_casualty = controller.choose_yes_no("Use Casualty 1 to copy the spell?")
            except Exception:
                do_casualty = False
            if not do_casualty:
                return

            try:
                sac_target = controller.choose_card(eligible, "Sacrifice a creature for Casualty 1")
            except Exception:
                sac_target = eligible[0]
            if sac_target is None:
                return

            sacrifice(game, controller, sac_target)

            # Find the top instant/sorcery stack object to copy
            original_stack_obj = None
            for sobj in game.stack.objects():
                spell = sobj.source
                ctypes = getattr(spell, "card_types", set())
                if CardType.INSTANT in ctypes or CardType.SORCERY in ctypes:
                    if sobj.controller is controller:
                        original_stack_obj = sobj
                        break

            if original_stack_obj is None:
                return

            # Create a copy
            copy_obj = copy_spell(game, original_stack_obj, controller)
            game.stack.push(copy_obj)

        controller_ref = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_casualty_effect,
            source=self,
            controller=controller_ref,
        ))

