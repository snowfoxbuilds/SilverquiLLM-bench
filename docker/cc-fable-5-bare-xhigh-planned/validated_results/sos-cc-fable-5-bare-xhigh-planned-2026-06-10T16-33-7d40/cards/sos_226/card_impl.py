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
    that spell, you may sacrifice a creature with power 1 or greater.
    When you do, copy the spell and you may choose new targets for the
    copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
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

    def register_triggers(self, game: GameState) -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: GameState, event: Any) -> bool:
            if getattr(event, "controller", None) is not source.controller:
                return False
            card = getattr(event, "card", None)
            if card is None or not (
                getattr(card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            ):
                return False
            source._pending_spell = getattr(event, "spell", None)
            return True

        def _effect(game: GameState) -> None:
            ctrl = source.controller
            stack_obj = getattr(source, "_pending_spell", None)
            if ctrl is None or stack_obj is None:
                return
            # The original must still be on the stack to be copied.
            if not any(item is stack_obj for item in game.stack.objects()):
                return

            candidates = [
                c for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return
            # One prompt: the creature to sacrifice, or None to decline.
            chosen = ctrl.choose_card(
                candidates,
                "Casualty 1 — sacrifice a creature with power 1 or greater "
                "(None to decline)",
            )
            if chosen is None or chosen not in candidates:
                return
            sacrifice(game, ctrl, chosen)

            # Copy the spell; the controller may choose new targets
            # (mirrors fdn_248 Thousand-Year Storm).
            new_targets: list[Any] | None = None
            if stack_obj.targets:
                if ctrl.choose_yes_no(
                    f"Choose new targets for copy of {stack_obj.source.name}?"
                ):
                    requirements = getattr(
                        stack_obj.source, "get_targets", lambda _: []
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

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=self.controller,
        ))
