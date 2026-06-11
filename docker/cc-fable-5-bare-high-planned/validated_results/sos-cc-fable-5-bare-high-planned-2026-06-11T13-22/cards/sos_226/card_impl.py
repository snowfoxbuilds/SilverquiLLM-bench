"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Creature —
    Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast
    that spell, you may sacrifice a creature with power 1 or greater. When
    you do, copy the spell and you may choose new targets for the copy.)

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

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or event.controller is not ctrl:
                return False
            card = event.card
            if card is source:
                return False
            if not getattr(card, "card_types", set()) & {
                CardType.INSTANT, CardType.SORCERY
            }:
                return False
            source._pending_so = event.spell
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = source.controller
            if ctrl is None:
                return
            original_so = getattr(source, "_pending_so", None)
            if original_so is None:
                return
            # The original spell must still be on the stack to be copied.
            if original_so not in game.stack._items:  # noqa: SLF001
                return

            bf = game.get_battlefield(ctrl)
            candidates = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return  # casualty simply not taken
            chosen = ctrl.choose_card(
                candidates,
                "Casualty 1 — sacrifice a creature with power 1 or greater "
                "(None to decline)",
            )
            if chosen is None or chosen not in candidates:
                return
            if getattr(chosen, "power", 0) < 1:
                return
            sacrifice(game, ctrl, chosen)

            # Copy the spell; the controller may choose new targets.
            new_targets: list[Any] | None = None
            if original_so.targets:
                if ctrl.choose_yes_no(
                    f"Choose new targets for copy of {original_so.source.name}?"
                ):
                    requirements = getattr(
                        original_so.source, "get_targets", lambda _g: []
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
            copy_obj = copy_spell(game, original_so, ctrl, new_targets)
            game.stack.push(copy_obj)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
