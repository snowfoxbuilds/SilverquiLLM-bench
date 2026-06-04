"""Card implementation for Silverquill, the Disputant (SOS #226)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 Legendary Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.

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
            "casualty 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        from engine.stack import copy_spell
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not ctrl:
                return False
            spell = getattr(event, "spell", None)
            card = getattr(spell, "source", None) if spell is not None else None
            card = card or getattr(event, "card", None)
            types = getattr(card, "card_types", set())
            if not types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            source._pending_card = card
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import sacrifice

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            pending_card = getattr(source, "_pending_card", None)
            if pending_card is None:
                return

            sac_options = [
                obj
                for obj in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "power", 0) >= 1
            ]
            if not sac_options:
                return
            if not ctrl.choose_yes_no(
                "Casualty 1: sacrifice a creature with power 1 or greater?"
            ):
                return
            chosen_sac = ctrl.choose(
                sac_options, "choose a creature to sacrifice for casualty"
            )
            if chosen_sac is None or not game.get_battlefield(ctrl).contains(chosen_sac):
                return

            # Locate the original spell on the stack before sacrificing.
            original_so = None
            for so in game.stack._items:
                if so.source is pending_card:
                    original_so = so
                    break
            if original_so is None:
                return

            sacrifice(game, ctrl, chosen_sac)

            new_targets: list[Any] | None = None
            if original_so.targets and ctrl.choose_yes_no(
                f"Choose new targets for the copy of {pending_card.name}?"
            ):
                new_targets = _choose_new_targets(game, ctrl, original_so)

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


def _choose_new_targets(game: "GameState", ctrl: Any, original_so: Any) -> list[Any]:
    requirements = getattr(original_so.source, "get_targets", lambda _g: [])(game)
    new_targets: list[Any] = []
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
    return new_targets
