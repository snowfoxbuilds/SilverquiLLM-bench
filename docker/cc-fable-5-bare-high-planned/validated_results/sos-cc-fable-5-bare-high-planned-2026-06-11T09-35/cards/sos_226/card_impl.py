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
            "casualty 1. (As you cast that spell, you may sacrifice a "
            "creature with power 1 or greater. When you do, copy the spell "
            "and you may choose new targets for the copy.)",
        )
        super().__init__(**kwargs)
        # Stack of pending cast StackObjects awaiting the casualty choice.
        self._pending_spells: list[Any] = []

    def register_triggers(self, game: "GameState") -> None:
        """Casualty 1 on the controller's instant/sorcery spells."""
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or event.controller is not ctrl:
                return False
            card_types = getattr(event.card, "card_types", set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            source._pending_spells.append(event.spell)
            return True

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            stack_obj = (
                source._pending_spells.pop() if source._pending_spells else None
            )
            if ctrl is None or stack_obj is None:
                return
            candidates = [
                c for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return  # casualty simply not taken
            chosen = ctrl.choose_card(
                candidates,
                "Casualty 1 — sacrifice a creature with power 1 or greater? "
                "(None to decline)",
            )
            if chosen is None or chosen not in candidates:
                return
            sacrifice(game, ctrl, chosen)
            # Copy only if the original spell is still on the stack.
            if not any(so is stack_obj for so in game.stack.objects()):
                return
            new_targets: list[Any] | None = None
            if stack_obj.targets:
                if ctrl.choose_yes_no(
                    f"Choose new targets for the copy of "
                    f"{getattr(stack_obj.source, 'name', 'the spell')}?"
                ):
                    requirements = getattr(
                        stack_obj.source, "get_targets", lambda _g: []
                    )(game)
                    new_targets = []
                    for req in requirements:
                        legal: list[Any] = []
                        for p in game.players:
                            for obj in game.get_battlefield(p).get_all():
                                if req.filter_fn(obj):
                                    legal.append(obj)
                            if req.filter_fn(p):
                                legal.append(p)
                        if legal:
                            new_targets.append(ctrl.choose_target(legal, req))
            copy_obj = copy_spell(game, stack_obj, ctrl, new_targets)
            game.stack.push(copy_obj)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
