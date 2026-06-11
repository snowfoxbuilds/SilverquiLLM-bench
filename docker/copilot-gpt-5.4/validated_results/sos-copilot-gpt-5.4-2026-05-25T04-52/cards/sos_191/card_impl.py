"""Card implementation for Geometer's Arthropod."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import look_at_cards, put_cards_on_bottom_in_random_order
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GeometersArthropod(Creature):
    """Geometer's Arthropod."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Geometer's Arthropod")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{U}"))
        kwargs.setdefault("subtypes", {"Fractal", "Crab"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            mana_cost = getattr(spell, "mana_cost", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
                and spell is not None
                and int(getattr(mana_cost, "x_count", 0)) > 0
            )

        def _effect(_game: GameState) -> None:
            return

        def _create_stack_object(_game: GameState, event: SpellCastTriggeredEvent) -> StackObject | None:
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            if current_controller is None or spell is None:
                return None
            x_value = max(0, int(getattr(spell, "x_value", 0)))

            def _resolve(
                game_at_resolution: GameState,
                *,
                amount: int = x_value,
                player=current_controller,
            ) -> None:
                if amount <= 0:
                    return
                library = game_at_resolution.get_library(player)
                looked_at = list(library.top(amount))
                if not looked_at:
                    return
                look_at_cards(
                    game_at_resolution,
                    player,
                    looked_at,
                    source=source,
                    reason="Geometer's Arthropod",
                )
                chosen = None
                try:
                    chosen = player.choose_card(
                        looked_at,
                        "Choose a card to put into your hand",
                    )
                except Exception:
                    chosen = looked_at[0]
                if chosen not in looked_at:
                    chosen = looked_at[0]
                for card in looked_at:
                    if library.contains(card):
                        library.remove(card)
                game_at_resolution.get_hand(player).add(chosen)
                remaining = [card for card in looked_at if card is not chosen]
                if remaining:
                    put_cards_on_bottom_in_random_order(
                        game_at_resolution,
                        player,
                        remaining,
                        source=source,
                        reason="Geometer's Arthropod",
                    )

            return StackObject(
                source=source,
                controller=current_controller,
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
