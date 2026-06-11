"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import create_token, exile
from benchmarks.sos.workspace.engine.player import Player
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _create_inkling_token() -> Creature:
    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
    )
    token.colors = {Color.WHITE, Color.BLACK}  # type: ignore[attr-defined]
    return token


class SwordsToPlowshares(Instant):
    """Prepared spell copy for Emeritus of Truce."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("rules_text", "Exile target creature. Its controller gains life equal to its power.")
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if not isinstance(target, Creature):
            return
        controller = getattr(target, "controller", None)
        if controller is None or not game.get_battlefield(controller).contains(target):
            return
        power = target.power
        exile(game, target)
        controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black Inkling creature "
            "token with flying. Then if an opponent controls more creatures than you, this creature "
            "becomes prepared.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Player),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target_player = targets[0] if targets else None
        if not isinstance(target_player, Player):
            return

        create_token(game, target_player, _create_inkling_token())

        controller = self.controller
        if controller is None:
            return

        your_count = sum(
            1 for permanent in game.get_battlefield(controller).get_all() if isinstance(permanent, Creature)
        )
        if not game.get_battlefield(controller).contains(self):
            your_count += 1
        opponent_has_more = any(
            sum(1 for permanent in game.get_battlefield(player).get_all() if isinstance(permanent, Creature))
            > your_count
            for player in game.players
            if player is not controller
        )
        if opponent_has_more:
            self.become_prepared()

    def create_prepared_spell_copy(self) -> Instant:
        return SwordsToPlowshares(owner=self.owner, controller=self.controller)
