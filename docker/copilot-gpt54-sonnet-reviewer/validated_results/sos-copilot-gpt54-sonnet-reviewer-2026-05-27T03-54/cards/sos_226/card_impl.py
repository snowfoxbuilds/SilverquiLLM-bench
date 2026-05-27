"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.game import sacrifice
from engine.stack import copy_spell
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from engine.stack import StackObject


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _eligible_casualty_creatures(game: "GameState", player: "Player", minimum_power: int) -> list[Any]:
    """Return creatures *player* can sacrifice to pay casualty."""
    eligible: list[Any] = []
    for permanent in game.get_battlefield(player).get_all():
        if CardType.CREATURE not in getattr(permanent, "card_types", set()):
            continue
        if getattr(permanent, "power", getattr(permanent, "base_power", 0)) < minimum_power:
            continue
        eligible.append(permanent)
    return eligible


def _choose_new_targets_for_copy(
    game: "GameState",
    controller: "Player",
    original_stack_object: "StackObject",
) -> list[Any] | None:
    """Return replacement targets for a casualty copy, if chosen."""
    if not original_stack_object.targets:
        return None
    if not controller.choose_yes_no(
        f"Choose new targets for casualty copy of {original_stack_object.source.name}?"
    ):
        return None

    requirements = getattr(original_stack_object.source, "get_targets", lambda _game: [])(game)
    new_targets: list[Any] = []
    for requirement in requirements:
        legal: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if requirement.filter_fn(obj):
                    legal.append(obj)
            if requirement.filter_fn(player):
                legal.append(player)
        chosen = controller.choose_target(legal, requirement)
        new_targets.append(chosen)
    return new_targets


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

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
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. (As you cast "
            "that spell, you may sacrifice a creature with power 1 or greater. "
            "When you do, copy the spell and you may choose new targets for the copy.)",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Grant your instants and sorceries a casualty-like cast trigger."""
        source = self
        controller = self.controller or self.owner or game.active_player

        def _condition(trigger_game: "GameState", event: Any) -> bool:
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            if getattr(event, "player", None) is not controller:
                return False
            if not _is_on_battlefield(trigger_game, source):
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            source._pending_casualty_spell = spell
            return True

        def _effect(trigger_game: "GameState") -> None:
            pending_spell = getattr(source, "_pending_casualty_spell", None)
            if pending_spell is None or controller is None:
                return

            eligible = _eligible_casualty_creatures(trigger_game, controller, minimum_power=1)
            if not eligible:
                return
            if not controller.choose_yes_no(f"Pay casualty 1 for {pending_spell.name}?"):
                return

            chosen = controller.choose_card(eligible, "creature to sacrifice for casualty 1")
            if chosen not in eligible:
                return

            sacrifice(trigger_game, controller, chosen)

            original_stack_object = None
            for stack_object in trigger_game.stack._items:  # noqa: SLF001
                if stack_object.source is pending_spell:
                    original_stack_object = stack_object
                    break
            if original_stack_object is None:
                return

            new_targets = _choose_new_targets_for_copy(trigger_game, controller, original_stack_object)
            trigger_game.stack.push(copy_spell(trigger_game, original_stack_object, controller, new_targets))

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
