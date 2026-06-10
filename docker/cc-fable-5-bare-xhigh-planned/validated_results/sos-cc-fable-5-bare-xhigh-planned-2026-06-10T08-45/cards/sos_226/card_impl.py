"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
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
        # Spells (StackObjects) awaiting their casualty decision, FIFO.
        self._casualty_pending: list[Any] = []

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.controller is not ctrl or ctrl is None:
                return False
            spell = event.card
            if not (_SPELL_TYPES & getattr(spell, "card_types", set())):
                return False
            source._casualty_pending.append(event.spell)
            return True

        def _effect(game: GameState) -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = getattr(source, "controller", None)
            if ctrl is None or not source._casualty_pending:
                return
            original_so = source._casualty_pending.pop(0)
            # Nothing to copy if the original already left the stack.
            if not any(item is original_so for item in game.stack._items):
                return
            eligible = [
                c
                for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not eligible:
                return
            try:
                chosen = ctrl.choose_card(
                    eligible,
                    "Casualty 1 — sacrifice a creature with power 1 or "
                    "greater to copy the spell (None to decline)",
                )
            except Exception:
                return
            if chosen is None or chosen not in eligible:
                return
            sacrifice(game, ctrl, chosen)

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

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
