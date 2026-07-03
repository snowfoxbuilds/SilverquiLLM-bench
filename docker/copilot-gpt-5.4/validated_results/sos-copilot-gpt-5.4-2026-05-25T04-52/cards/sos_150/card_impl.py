"""Card implementation for Glorious Decay."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant, Mode
from benchmarks.sos.workspace.engine.game import deal_damage, destroy, draw_card, exile
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _is_on_battlefield(game: GameState, obj: Any) -> bool:
    """Return whether *obj* is still on the battlefield."""
    return any(game.get_battlefield(player).contains(obj) for player in game.players)


def _is_in_graveyard(game: GameState, obj: Any) -> bool:
    """Return whether *obj* is still in any graveyard."""
    return any(game.get_graveyard(player).contains(obj) for player in game.players)


class GloriousDecay(Instant):
    """Glorious Decay."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Glorious Decay")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)
        self.selected_mode = 0

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Destroy target artifact", description="Destroy target artifact."),
            Mode(
                name="Deal 4 damage to target creature with flying",
                description="Glorious Decay deals 4 damage to target creature with flying.",
            ),
            Mode(
                name="Exile target card from a graveyard",
                description="Exile target card from a graveyard. Draw a card.",
            ),
        ]

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        if self.selected_mode == 0:
            return [
                TargetRequirement(
                    filter_fn=lambda obj: CardType.ARTIFACT in getattr(obj, "card_types", set()),
                    description="target artifact",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        if self.selected_mode == 1:
            return [
                TargetRequirement(
                    filter_fn=lambda obj: (
                        CardType.CREATURE in getattr(obj, "card_types", set())
                        and Keyword.FLYING in getattr(obj, "keywords", Keyword(0))
                    ),
                    description="target creature with flying",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        return [
            TargetRequirement(
                filter_fn=lambda _obj: True,
                description="target card in a graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        controller = self.controller
        if target is None:
            return
        if self.selected_mode == 0:
            if not _is_on_battlefield(game, target):
                return
            if CardType.ARTIFACT not in getattr(target, "card_types", set()):
                return
            destroy(game, target)
            return
        if self.selected_mode == 1:
            if not _is_on_battlefield(game, target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if Keyword.FLYING not in getattr(target, "keywords", Keyword(0)):
                return
            deal_damage(game, self, target, 4)
            return
        if not _is_in_graveyard(game, target):
            return
        exile(game, target)
        if controller is not None:
            draw_card(game, controller)
