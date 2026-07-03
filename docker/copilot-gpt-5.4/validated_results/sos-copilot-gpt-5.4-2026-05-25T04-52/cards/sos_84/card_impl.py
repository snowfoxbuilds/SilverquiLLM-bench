"""Card implementation for Forum Necroscribe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import discard
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class ForumNecroscribe(Creature):
    """Forum Necroscribe."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Forum Necroscribe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}"))
        kwargs.setdefault("subtypes", {"Troll", "Warlock"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Ward—Discard a card.\nRepartee — Whenever you cast an instant or sorcery spell "
            "that targets a creature, return target creature card from your graveyard to the battlefield.",
        )
        super().__init__(**kwargs)
        self.ward_cost = self._pay_discard_ward

    def _pay_discard_ward(
        self,
        game: GameState,
        player: Player,
        taxed_spell: object,  # noqa: ARG002
        taxed_stack_obj: StackObject,  # noqa: ARG002
    ) -> bool:
        hand = game.get_hand(player).get_all()
        if not hand:
            return False
        if not player.choose_yes_no("Discard a card to pay ward?"):
            return False
        try:
            chosen = player.choose_card(hand, "card to discard for ward")
        except Exception:
            chosen = hand[0]
        if chosen is None or not game.get_hand(player).contains(chosen):
            return False
        discard(game, player, chosen)
        return True

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or event.player is not current_controller:
                return False
            spell = event.spell
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            return any(
                isinstance(target, Creature) and target.is_on_battlefield(game)
                for target in getattr(spell, "_casting_targets", [])
            )

        def _effect(game: GameState) -> None:
            return

        def _create_stack_object(game: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return None
            graveyard = game.get_graveyard(current_controller)
            target_spec = TargetRequirement(
                filter_fn=lambda obj, _graveyard=graveyard: isinstance(obj, Creature) and _graveyard.contains(obj),
                description="target creature card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
            candidates = [card for card in graveyard.get_all() if target_spec.filter_fn(card)]
            if not candidates:
                return None
            try:
                chosen = current_controller.choose_target([target_spec], target_spec)
            except Exception:
                chosen = candidates[0]
            if chosen not in candidates:
                chosen = candidates[0]

            def _resolve(g: GameState, *, target: Creature = chosen) -> None:
                controller_at_resolution = getattr(source, "controller", None)
                if controller_at_resolution is None:
                    return
                controller_graveyard = g.get_graveyard(controller_at_resolution)
                if not controller_graveyard.contains(target):
                    return
                target.controller = controller_at_resolution
                move_to_zone(g, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

            return StackObject(
                source=source,
                controller=current_controller,
                targets=[chosen],
                on_resolve=_resolve,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                create_stack_object=_create_stack_object,
            )
        )
