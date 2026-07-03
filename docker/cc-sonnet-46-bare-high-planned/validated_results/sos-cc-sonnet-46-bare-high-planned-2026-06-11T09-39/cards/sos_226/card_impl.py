"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon 4/4.

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
        """Register SpellCastTriggeredEvent handler for Casualty 1."""
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _casualty_condition(game: Any, event: Any) -> bool:
            """Fire when the controller casts an instant or sorcery."""
            # Only for spells cast by this permanent's controller.
            if event.controller is not source.controller:
                return False
            card = event.card
            if card is None:
                return False
            types = getattr(card, "card_types", set())
            return CardType.INSTANT in types or CardType.SORCERY in types

        def _casualty_effect(game: Any) -> None:
            """Offer casualty: sacrifice power ≥ 1 creature to copy the spell."""
            ctrl = source.controller
            if ctrl is None:
                return

            # Find creatures with power ≥ 1 on controller's battlefield.
            bf = game.get_battlefield(ctrl)
            eligible = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
                and c is not source  # Can still sacrifice Silverquill itself
            ]
            # Actually the card says "a creature" — Silverquill itself qualifies
            # as it has power 4, but let's include it per rules.
            # Re-gather without the exclusion:
            eligible = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not eligible:
                return

            # Offer the player a choice: pick a creature or None to decline.
            try:
                chosen_creature = ctrl.choose_card(eligible, "Casualty 1: sacrifice a creature with power ≥ 1 (or None to decline)")
            except Exception:
                return

            if chosen_creature is None or chosen_creature not in eligible:
                return

            # Sacrifice the chosen creature.
            sacrifice(game, ctrl, chosen_creature)

            # The original spell should be on the stack; find the most recently
            # pushed instant/sorcery spell object.
            original = None
            for stack_obj in reversed(game.stack._items):
                card = stack_obj.source
                types = getattr(card, "card_types", set())
                if CardType.INSTANT in types or CardType.SORCERY in types:
                    original = stack_obj
                    break

            if original is None:
                return

            # Copy the spell; controller may choose new targets.
            copy_obj = copy_spell(game, original, ctrl)
            # Let the player choose new targets for the copy via the player script.
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_casualty_condition,
                effect=_casualty_effect,
                source=self,
                controller=controller,
            )
        )
