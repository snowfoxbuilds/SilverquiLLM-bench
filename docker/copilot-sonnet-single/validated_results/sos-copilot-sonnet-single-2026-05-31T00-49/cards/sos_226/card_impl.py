"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon — 4/4.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1 or
    greater. When you do, copy the spell and you may choose new targets for
    the copy.)

    ENGINE LIMITATION: Casualty is implemented as a post-cast hook. When
    an instant/sorcery is cast while Silverquill is on the battlefield, the
    controller is offered the casualty choice. If they sacrifice a creature
    with power ≥ 1, a copy of the spell is pushed onto the stack.

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

    # ------------------------------------------------------------------
    # Casualty trigger — fires whenever controller casts an instant/sorcery
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register a SpellCast trigger to offer casualty 1."""
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import StackObject
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Only trigger for spells cast by the controller.
            spell_ctrl = getattr(event, "controller", None) or getattr(event, "player", None)
            if spell_ctrl is not ctrl:
                return False
            # Only for instants and sorceries.
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Don't trigger on itself (it's a creature, not an instant/sorcery).
            return spell is not source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Find legal casualty targets (creatures with power ≥ 1 ctrl controls).
            bf = game.get_battlefield(ctrl)
            legal = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
                and c is not source  # can sacrifice Silverquill itself but keep it simple
            ]
            if not legal:
                return
            # Ask controller if they want to sacrifice.
            try:
                want = ctrl.choose_yes_no("Sacrifice a creature for casualty 1?")
            except Exception:
                return
            if not want:
                return
            # Choose which creature to sacrifice.
            try:
                victim = ctrl.choose_card(legal, "Choose creature to sacrifice for casualty")
                if isinstance(victim, int):
                    victim = legal[victim] if 0 <= victim < len(legal) else None
            except Exception:
                victim = legal[0] if legal else None
            if victim is None:
                return
            sacrifice(game, ctrl, victim)
            # Copy the most recently cast spell (top of stack).
            if game.stack.is_empty():
                return
            original = game.stack.peek()
            if original is None:
                return
            # Create a copy of the stack object.
            import copy as _copy
            spell_copy = _copy.copy(original.source)
            spell_copy.controller = ctrl
            targets_copy = list(original.targets) if original.targets else []

            def _copy_resolve(g: "GameState") -> None:
                spell_copy.chosen_targets = targets_copy
                spell_copy.on_resolve(g)

            copy_obj = StackObject(
                source=spell_copy,
                controller=ctrl,
                targets=targets_copy,
                on_resolve=_copy_resolve,
            )
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

