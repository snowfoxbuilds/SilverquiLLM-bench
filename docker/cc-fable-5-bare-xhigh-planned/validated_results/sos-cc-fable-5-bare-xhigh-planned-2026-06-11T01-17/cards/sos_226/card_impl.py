"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


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

    def register_triggers(self, game: GameState) -> None:
        """Casualty 1 on your instant/sorcery casts (fires off E1's event)."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if ctrl is None or caster is not ctrl:
                return False
            spell = getattr(event, "card", None)
            if spell is None or spell is source:
                return False
            if not getattr(spell, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}:
                return False
            source._casualty_spell = event.spell  # the StackObject
            return True

        def _effect(game: GameState) -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = getattr(source, "controller", None)
            original_so = getattr(source, "_casualty_spell", None)
            if ctrl is None or original_so is None:
                return
            # Spell may have left the stack (e.g. countered) — then no copy.
            if original_so not in game.stack._items:  # noqa: SLF001
                return

            candidates = [
                c
                for c in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not candidates:
                return  # casualty simply not taken
            # One prompt: the answer is the creature to sacrifice, or None
            # to decline the casualty.
            chosen = ctrl.choose_card(
                candidates, "Casualty 1 — sacrifice a creature with power 1 "
                "or greater (None to decline)"
            )
            if chosen is None or chosen not in candidates:
                return
            sacrifice(game, ctrl, chosen)

            # Copy the spell; the controller may choose new targets.
            new_targets: list[Any] | None = None
            if original_so.targets:
                if ctrl.choose_yes_no(
                    f"Choose new targets for copy of "
                    f"{getattr(original_so.source, 'name', 'spell')}?"
                ):
                    requirements = original_so.source.get_targets(game)
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
