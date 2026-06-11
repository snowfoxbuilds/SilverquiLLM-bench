"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState

_MANA_COST = ManaCost(generic=2, pips={ManaType.WHITE: 1, ManaType.BLACK: 1})


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
        kwargs.setdefault("mana_cost", _MANA_COST)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\nEach instant and sorcery spell you cast has "
            "casualty 1. (As you cast that spell, you may sacrifice a creature "
            "with power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register casualty 1 trigger on SpellCastTriggeredEvent (E1)."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            # Only fire for instant/sorcery spells cast by our controller.
            caster = getattr(event, "controller", None)
            if caster is not source.controller:
                return False
            spell_card = getattr(event, "card", None)
            if spell_card is None:
                return False
            # Don't trigger off Silverquill itself being cast.
            if spell_card is source:
                return False
            card_types = getattr(spell_card, "card_types", set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return

            # Find creatures with power >= 1 that the controller can sacrifice.
            bf = g.get_battlefield(ctrl)
            candidates = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
                and c is not source  # can sacrifice Silverquill itself if power≥1
            ]

            if not candidates:
                return

            # Prompt: choose a creature to sacrifice (or None to decline).
            try:
                chosen = ctrl.choose_card(
                    candidates + [None],
                    "Casualty 1: sacrifice a creature with power 1 or greater? (None to skip)",
                )
            except Exception:
                return

            if chosen is None:
                return

            # Validate the choice is a legal sacrifice target.
            if not bf.contains(chosen):
                return
            if getattr(chosen, "power", 0) < 1:
                return

            # Sacrifice the creature.
            from engine.game import sacrifice
            sacrifice(g, ctrl, chosen)

            # Find the original spell on the stack (the most recently cast IS spell).
            original_so = None
            for so in reversed(g.stack._items):
                card = getattr(so, "source", None)
                if card is None:
                    continue
                card_types = getattr(card, "card_types", set())
                if card_types & {CardType.INSTANT, CardType.SORCERY}:
                    if getattr(so, "controller", None) is ctrl:
                        original_so = so
                        break

            if original_so is None:
                return

            # Allow player to choose new targets for the copy.
            from engine.stack import copy_spell
            new_targets = None
            if getattr(original_so, "targets", None):
                try:
                    if ctrl.choose_yes_no("Choose new targets for the copy?"):
                        requirements = getattr(
                            original_so.source, "get_targets", lambda _: []
                        )(g)
                        new_targets = []
                        for req in requirements:
                            legal = []
                            for p in g.players:
                                for obj in g.get_battlefield(p).get_all():
                                    fn = getattr(req, "filter_fn", None)
                                    if fn and fn(obj):
                                        legal.append(obj)
                                fn = getattr(req, "filter_fn", None)
                                if fn and fn(p):
                                    legal.append(p)
                            if legal:
                                t = ctrl.choose_target(legal, req)
                                new_targets.append(t)
                except Exception:
                    new_targets = None

            copy_obj = copy_spell(g, original_so, ctrl, new_targets)
            g.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
