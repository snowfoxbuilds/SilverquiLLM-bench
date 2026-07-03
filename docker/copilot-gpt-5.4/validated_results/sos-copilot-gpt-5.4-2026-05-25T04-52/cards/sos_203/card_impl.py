"""Card implementation for Mind Roots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Land, Sorcery
from benchmarks.sos.workspace.engine.game import discard
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MindRoots(Sorcery):
    """Mind Roots."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mind Roots")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Target player discards two cards. You may put a land card discarded this way "
            "onto the battlefield tapped under your control.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "zones"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        targets = getattr(self, "chosen_targets", [])
        target_player = targets[0] if targets else None
        if controller is None or target_player is None or not hasattr(target_player, "zones"):
            return

        discarded_lands: list[Land] = []
        for _ in range(2):
            hand_cards = list(game.get_hand(target_player).get_all())
            if not hand_cards:
                break
            chosen_card = target_player.choose_card(hand_cards, "Choose a card to discard")
            if chosen_card is None or not game.get_hand(target_player).contains(chosen_card):
                continue
            discard(game, target_player, chosen_card)
            if isinstance(chosen_card, Land):
                discarded_lands.append(chosen_card)

        if not discarded_lands:
            return
        if not controller.choose_yes_no("Put a discarded land onto the battlefield tapped?"):
            return
        chosen_land = controller.choose_card(
            discarded_lands,
            "Choose a land card discarded this way",
        )
        if chosen_land not in discarded_lands or not game.get_graveyard(target_player).contains(chosen_land):
            return
        chosen_land.controller = controller
        chosen_land.is_tapped = True
        move_to_zone(game, chosen_land, Zone.GRAVEYARD, Zone.BATTLEFIELD)
