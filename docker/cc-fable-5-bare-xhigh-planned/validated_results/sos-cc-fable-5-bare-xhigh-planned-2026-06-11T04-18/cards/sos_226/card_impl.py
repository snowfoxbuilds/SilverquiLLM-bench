"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
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

    def register_triggers(self, game: GameState) -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            if card is None or not (_SPELL_TYPES & getattr(card, "card_types", set())):
                return False
            if not g.get_battlefield(ctrl).contains(source):
                return False
            source._pending_casualty = event.spell
            return True

        def _effect(g: GameState) -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            original = getattr(source, "_pending_casualty", None)
            if original is None:
                return
            source._pending_casualty = None

            eligible = [
                c
                for c in g.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]
            if not eligible:
                return  # casualty simply not taken
            try:
                chosen = ctrl.choose_card(
                    eligible,
                    "casualty 1 — sacrifice a creature with power 1 or "
                    "greater to copy the spell (None to decline)",
                )
            except Exception:
                chosen = None
            if chosen is None or chosen not in eligible:
                return
            sacrifice(g, ctrl, chosen)

            # Copy the spell; the controller may choose new targets
            # (mirrors fdn_248 Thousand-Year Storm).
            new_targets: list[Any] | None = None
            if original.targets:
                try:
                    redo = ctrl.choose_yes_no(
                        f"Choose new targets for copy of {original.source.name}?"
                    )
                except Exception:
                    redo = False
                if redo:
                    requirements = getattr(
                        original.source, "get_targets", lambda _g: []
                    )(g)
                    new_targets = []
                    for req in requirements:
                        legal: list[Any] = []
                        for p in g.players:
                            for obj in g.get_battlefield(p).get_all():
                                if req.filter_fn(obj):
                                    legal.append(obj)
                            if req.filter_fn(p):
                                legal.append(p)
                        if legal:
                            new_targets.append(ctrl.choose_target(legal, req))
            copy_obj = copy_spell(g, original, ctrl, new_targets)
            g.stack.push(copy_obj)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
