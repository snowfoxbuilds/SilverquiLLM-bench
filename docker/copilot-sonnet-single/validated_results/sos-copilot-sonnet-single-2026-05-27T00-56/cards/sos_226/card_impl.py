"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon — 4/4.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)
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
            (
                "Flying, vigilance\n"
                "Each instant and sorcery spell you cast has casualty 1. "
                "(As you cast that spell, you may sacrifice a creature with "
                "power 1 or greater. When you do, copy the spell and you may "
                "choose new targets for the copy.)"
            ),
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the casualty 1 trigger for instants and sorceries cast."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # Mutable container to capture the spell from the triggering event.
        _captured: dict[str, Any] = {}

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            """Fire when controller casts an instant or sorcery while on battlefield."""
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Silverquill must be on the battlefield.
            bf = game.get_battlefield(ctrl)
            if not bf.contains(source):
                return False
            # The spell must be cast by the controller.
            event_controller = getattr(event, "controller", None) or getattr(event, "player", None)
            if event_controller is not ctrl:
                return False
            # The spell must be an instant or sorcery.
            spell = getattr(event, "spell", None)
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Capture the spell for the effect closure.
            _captured["spell"] = spell
            return True

        def _effect(game: "GameState") -> None:
            """Casualty 1: optionally sacrifice a creature to copy the spell."""
            from engine.stack import StackObject, copy_spell
            from engine.player import ScriptExhaustedError

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Find eligible sacrifice targets: creatures controlled by the
            # controller with power >= 1.
            bf = game.get_battlefield(ctrl)
            eligible = []
            for perm in bf.get_all():
                perm_card_types = getattr(perm, "card_types", set())
                if CardType.CREATURE not in perm_card_types:
                    continue
                perm_power = getattr(perm, "base_power", 0)
                if perm_power >= 1:
                    eligible.append(perm)

            if not eligible:
                return

            # Ask player whether to pay the casualty cost.
            try:
                wants_to_pay = ctrl.choose_yes_no(
                    "Silverquill, the Disputant: Pay casualty 1? (sacrifice a creature with power 1 or greater)"
                )
            except (ScriptExhaustedError, NotImplementedError):
                wants_to_pay = False
            if not wants_to_pay:
                return

            # Choose a creature to sacrifice.
            try:
                creature = ctrl.choose_card(
                    eligible,
                    "Silverquill, the Disputant: choose a creature to sacrifice for casualty 1",
                )
            except (ScriptExhaustedError, NotImplementedError):
                creature = eligible[0]

            if creature is None:
                return

            # Sacrifice the chosen creature (move to graveyard).
            from engine.zones import move_to_zone
            move_to_zone(game, creature, Zone.BATTLEFIELD, Zone.GRAVEYARD)

            # Find the original StackObject for the spell so we can copy targets.
            spell = _captured.get("spell")
            if spell is None:
                return

            original_so = None
            for so in game.stack._items:
                if so.source is spell:
                    original_so = so
                    break

            # Create a copy of the spell with an independent targets list.
            if original_so is not None:
                copy_so = copy_spell(game, original_so, ctrl)
            else:
                # Fallback: create copy without targets info (no original on stack).
                spell_copy = copy.copy(spell)
                copy_so = StackObject(source=spell_copy, controller=ctrl)

            # Ask if the player wants to choose new targets for the copy
            # (oracle: "you may choose new targets for the copy").
            try:
                wants_new_targets = ctrl.choose_yes_no(
                    "Silverquill, the Disputant: Choose new targets for the copy?"
                )
            except (ScriptExhaustedError, NotImplementedError):
                wants_new_targets = False

            if wants_new_targets:
                try:
                    new_target = ctrl.choose_card(
                        [],
                        "Silverquill, the Disputant: choose new target for the copy",
                    )
                    if new_target is not None:
                        copy_so.targets = [new_target]
                except (ScriptExhaustedError, NotImplementedError):
                    pass

            game.stack.push(copy_so)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
