"""Card implementation for Emeritus of Ideation // Ancestral Recall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class AncestralRecall(Instant):
    """Prepared spell copy for Emeritus of Ideation."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ancestral Recall")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class EmeritusOfIdeationAncestralRecall(Creature):
    """Emeritus of Ideation."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Ideation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.WARD)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)
        self.ward_cost = ManaCost.parse("{2}")

    def _choose_graveyard_cards_to_exile(self, game: GameState) -> list[object]:
        controller = getattr(self, "controller", None)
        if controller is None:
            return []
        graveyard_cards = list(game.get_graveyard(controller).get_all())
        if len(graveyard_cards) < 8:
            return []
        if len(graveyard_cards) == 8:
            return graveyard_cards

        chosen: list[object] = []
        remaining = list(graveyard_cards)
        for index in range(8):
            selection = None
            try:
                candidate = controller.choose_card(
                    remaining,
                    f"Choose card to exile for Emeritus of Ideation ({index + 1}/8)",
                )
            except Exception:
                candidate = None
            if candidate in remaining:
                selection = candidate
            if selection is None:
                selection = remaining[0]
            chosen.append(selection)
            remaining.remove(selection)
        return chosen

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Instant:
        return AncestralRecall(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: AttacksTriggeredEvent) -> bool:  # noqa: ARG001
            return event.attacker is source or event.creature is source

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            graveyard = game.get_graveyard(current_controller)
            cards = graveyard.get_all()
            try:
                should_prepare = current_controller.choose_yes_no(
                    "Exile eight cards from your graveyard to become prepared?"
                )
            except Exception:
                should_prepare = False
            if not should_prepare or len(cards) < 8:
                return
            chosen_cards = source._choose_graveyard_cards_to_exile(game)
            if len(chosen_cards) != 8:
                return
            for card in chosen_cards:
                move_to_zone(game, card, Zone.GRAVEYARD, Zone.EXILE)
            source.become_prepared()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
