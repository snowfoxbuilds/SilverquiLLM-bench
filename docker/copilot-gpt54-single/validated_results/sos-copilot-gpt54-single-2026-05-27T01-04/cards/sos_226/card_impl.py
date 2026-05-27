"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from engine.stack import StackObject


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

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
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power "
            "1 or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    def granted_casualty_value_for(
        self,
        game: GameState,
        player: Player,
        spell: Any,
    ) -> int | None:
        """Grant casualty 1 to your instant and sorcery spells."""
        del game
        if getattr(self, "controller", None) is not player:
            return None
        if CardType.INSTANT not in getattr(spell, "card_types", set()) and CardType.SORCERY not in getattr(spell, "card_types", set()):
            return None
        return 1

    @staticmethod
    def _legal_targets_for_requirement(game: GameState, requirement: Any) -> list[Any]:
        """Return a best-effort list of legal retarget choices for a copied spell."""
        legal_targets: list[Any] = []
        zone = getattr(requirement, "zone", None)
        filter_fn = getattr(requirement, "filter_fn", None)
        if filter_fn is None:
            return legal_targets

        if zone == Zone.STACK:
            for stack_obj in game.stack.objects():
                if filter_fn(stack_obj):
                    legal_targets.append(stack_obj)
            return legal_targets

        for player in game.players:
            if filter_fn(player):
                legal_targets.append(player)

            if zone == Zone.BATTLEFIELD:
                objects = game.get_battlefield(player).get_all()
            elif zone is not None:
                objects = player.zones[zone].get_all()
            else:
                objects = []

            for obj in objects:
                if filter_fn(obj):
                    legal_targets.append(obj)

        return legal_targets

    def _choose_new_targets_for_copy(
        self,
        game: GameState,
        controller: Player,
        original_stack_obj: StackObject,
    ) -> list[Any] | None:
        """Optionally choose new targets for the casualty-created spell copy."""
        if not original_stack_obj.targets:
            return None

        if not controller.choose_yes_no(
            f"Choose new targets for copy of {original_stack_obj.source.name}?"
        ):
            return None

        requirements = getattr(original_stack_obj.source, "get_targets", lambda _game: [])(game)
        if not requirements:
            return None

        new_targets = list(original_stack_obj.targets)
        for index, requirement in enumerate(requirements):
            legal_targets = self._legal_targets_for_requirement(game, requirement)
            if not legal_targets:
                continue
            chosen_target = controller.choose_target(legal_targets, requirement)
            if chosen_target not in legal_targets:
                continue
            if index < len(new_targets):
                new_targets[index] = chosen_target
            else:
                new_targets.append(chosen_target)

        return new_targets

    def snapshot_granted_casualty_trigger(
        self,
        spell: Any,
        controller: Player | None,
    ) -> dict[str, Any]:
        """Snapshot the casualty-copy trigger so it survives the source leaving."""
        locked_controller = controller or getattr(self, "controller", None)
        return {
            "source": self,
            "controller": locked_controller,
            "effect": self._create_granted_casualty_effect(spell, locked_controller),
        }

    def _create_granted_casualty_effect(
        self,
        spell: Any,
        controller: Player | None,
    ) -> Any:
        """Build the casualty-copy effect for a specific cast spell."""
        from engine.stack import copy_spell

        source = self
        locked_controller = controller

        def _effect(game: GameState) -> None:
            if spell is None or locked_controller is None:
                return

            original_stack_obj = None
            for stack_obj in game.stack.objects():
                if stack_obj.source is spell:
                    original_stack_obj = stack_obj
                    break

            if original_stack_obj is None:
                return

            new_targets = source._choose_new_targets_for_copy(
                game,
                locked_controller,
                original_stack_obj,
            )
            game.stack.push(copy_spell(game, original_stack_obj, locked_controller, new_targets))

        return _effect

    def register_triggers(self, game: GameState) -> None:
        """Register the granted casualty trigger watcher."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            del game
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False

            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not getattr(source, "controller", None):
                return False

            card_types = getattr(spell, "card_types", set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False

            if getattr(spell, "_granted_casualty_available", False):
                return bool(getattr(spell, "_granted_casualty_paid", False))

            return True

        def _effect_factory(
            _game: GameState,
            event: SpellCastTriggeredEvent,
        ) -> Any:
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            locked_controller = getattr(source, "controller", None) or controller
            return source._create_granted_casualty_effect(spell, locked_controller)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=lambda _game: None,
                effect_factory=_effect_factory,
                source=self,
                controller=controller,
            )
        )
