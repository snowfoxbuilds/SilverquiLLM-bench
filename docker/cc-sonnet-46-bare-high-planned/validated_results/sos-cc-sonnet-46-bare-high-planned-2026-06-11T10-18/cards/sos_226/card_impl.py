"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon 4/4.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1 or greater.
    When you do, copy the spell and you may choose new targets for the copy.)
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
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power 1 or greater. "
            "When you do, copy the spell and you may choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration
        from engine.game import sacrifice

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            # Fire for instant/sorcery spells cast by Silverquill's controller.
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not source.controller:
                return False
            spell = getattr(event, "spell", None)
            if spell is None:
                return False
            card = getattr(spell, "source", spell)
            card_types = getattr(card, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return

            # Find the triggering spell on the stack.
            # It's the most recently pushed instant/sorcery stack object.
            target_so = None
            for so in reversed(g.stack._items):
                card = so.source
                card_types = getattr(card, "card_types", set())
                if (CardType.INSTANT in card_types or CardType.SORCERY in card_types) and so.controller is ctrl:
                    target_so = so
                    break

            if target_so is None:
                return

            # Find creatures with power >= 1 that the controller can sacrifice.
            bf = g.get_battlefield(ctrl)
            eligible = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]

            if not eligible:
                return

            # Prompt: choose a creature to sacrifice (None = decline).
            try:
                chosen_creature = ctrl.choose_card(eligible, "Sacrifice a creature for Casualty 1? (None to decline)")
            except Exception:
                chosen_creature = None

            if chosen_creature is None:
                return

            # Sacrifice must have power >= 1.
            if getattr(chosen_creature, "power", 0) < 1:
                return

            sacrifice(g, ctrl, chosen_creature)

            # Copy the spell. Controller may choose new targets.
            new_targets: list[Any] | None = None
            if target_so.targets:
                try:
                    want_new = ctrl.choose_yes_no("Choose new targets for the copy?")
                    if want_new:
                        new_targets = []
                        for _ in target_so.targets:
                            new_targets.append(ctrl.choose_target(None, "new target"))
                except Exception:
                    new_targets = None

            copy = copy_spell(g, target_so, ctrl, new_targets)
            g.stack.push(copy)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
