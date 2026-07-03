"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 Legendary Elder Dragon.

    Flying, vigilance.
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
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1. (As you cast that spell, you may sacrifice a creature "
            "with power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register SpellCastTriggeredEvent trigger for Casualty 1 granting."""
        from engine.events import SpellCastTriggeredEvent
        from engine.game import sacrifice
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None)
            if caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Find eligible sacrificial creatures: power >= 1, on controller's battlefield
            bf = game.get_battlefield(ctrl)
            candidates = [
                p for p in bf.get_all()
                if CardType.CREATURE in getattr(p, "card_types", set())
                and getattr(p, "power", 0) >= 1
                and p is not source  # Silverquill itself only eligible if explicitly scripted
            ]
            if not candidates:
                return

            # Prompt the player to choose a creature to sacrifice (None = decline)
            try:
                chosen = ctrl.choose_card(candidates, "sacrifice for Casualty 1?")
            except Exception:
                return
            if chosen is None or chosen not in candidates:
                return

            # Sacrifice the chosen creature
            sacrifice(game, ctrl, chosen)

            # Find the most-recently-pushed instant/sorcery on the stack
            original_so = None
            for so in reversed(list(game.stack._items)):
                if getattr(so, "controller", None) is ctrl and getattr(
                    getattr(so, "source", None), "card_types", set()
                ) & {CardType.INSTANT, CardType.SORCERY}:
                    original_so = so
                    break
            if original_so is None:
                return

            # Copy the spell; offer new targets if the spell has targets
            new_targets: list[Any] | None = None
            if original_so.targets:
                try:
                    if ctrl.choose_yes_no(
                        f"Choose new targets for copy of {original_so.source.name}?"
                    ):
                        requirements = getattr(
                            original_so.source, "get_targets", lambda _: []
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
                                new_targets.append(
                                    ctrl.choose_target(legal, req)
                                )
                except Exception:
                    pass

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
