"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


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
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not ctrl:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None or not _is_instant_or_sorcery(spell):
                return False
            source._casualty_spell = spell  # type: ignore[attr-defined]
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import sacrifice
            from engine.stack import copy_spell

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            spell = getattr(source, "_casualty_spell", None)
            if spell is None:
                return

            sacrificeable = [
                obj for obj in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "power", 0) >= 1
            ]
            if not sacrificeable:
                return
            if not ctrl.choose_yes_no("Apply casualty 1 — sacrifice a creature?"):
                return
            victim = ctrl.choose(sacrificeable, "creature to sacrifice (casualty 1)")
            if victim is None or victim not in sacrificeable:
                return

            sacrifice(game, ctrl, victim)

            original_so = None
            for so in game.stack._items:  # noqa: SLF001
                if so.source is spell:
                    original_so = so
                    break
            if original_so is None:
                return

            new_targets = self._choose_new_targets(game, ctrl, original_so)
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

    @staticmethod
    def _choose_new_targets(
        game: "GameState", ctrl: Any, original_so: Any
    ) -> list[Any] | None:
        if not original_so.targets:
            return None
        if not ctrl.choose_yes_no(
            f"Choose new targets for the copy of {original_so.source.name}?"
        ):
            return None
        requirements = original_so.source.get_targets(game)
        new_targets: list[Any] = []
        for req in requirements:
            legal: list[Any] = []
            for p in game.players:
                for obj in game.get_battlefield(p).get_all():
                    if req.filter_fn(obj):
                        legal.append(obj)
                if req.filter_fn(p):
                    legal.append(p)
            chosen = ctrl.choose_target(legal, req) if legal else None
            new_targets.append(chosen)
        return new_targets
