"""Card implementation for Seize the Spoils."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Artifact, ManaAbility, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.game import create_token, discard, draw_card, sacrifice
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class SeizeTheSpoils(Sorcery):
    """Seize the Spoils."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Seize the Spoils")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        controller = self.controller
        if controller is None:
            return True
        if getattr(self, "cast_from_zone", Zone.HAND) != Zone.HAND:
            return True
        hand = game.get_hand(controller).get_all()
        return any(card is not self for card in hand)

    def pay_additional_cast_costs(
        self,
        game: GameState,
        player: Player,
        from_zone: Zone,  # noqa: ARG002
    ) -> None:
        hand = game.get_hand(player).get_all()
        discardable = [card for card in hand if card is not self]
        if not discardable:
            raise CastingError(f"Cannot cast {self.name!r} — no card available to discard")
        chosen = player.choose_card(discardable, "card to discard")
        if chosen not in discardable:
            raise CastingError(f"Cannot cast {self.name!r} — invalid discard choice")
        discard(game, player, chosen)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        draw_card(game, controller)
        draw_card(game, controller)
        token = TreasureToken(owner=controller, controller=controller)
        create_token(game, controller, token)


class TreasureToken(Artifact):
    """Treasure token with a functional mana ability."""

    _COLOR_CHOICES = [
        ManaType.WHITE,
        ManaType.BLUE,
        ManaType.BLACK,
        ManaType.RED,
        ManaType.GREEN,
    ]

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Treasure")
        kwargs.setdefault("subtypes", {"Treasure"})
        kwargs.setdefault("rules_text", "{T}, Sacrifice this token: Add one mana of any color.")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: GameState, artifact: Artifact) -> bool:
            controller = source.controller
            if controller is None or artifact.is_tapped:
                return False
            if not game.get_battlefield(controller).contains(source):
                return False
            artifact.is_tapped = True
            sacrifice(game, controller, source)
            return True

        def _mana_produced(game: GameState) -> None:  # noqa: ARG001
            controller = source.controller
            if controller is None:
                return
            chosen_color = controller.choose(self._COLOR_CHOICES, "mana color for Treasure")
            if chosen_color not in self._COLOR_CHOICES:
                return
            controller.mana_pool.add(chosen_color, 1)

        return [
            ManaAbility(
                cost=_cost,
                mana_produced=_mana_produced,
                description="{T}, Sacrifice this token: Add one mana of any color.",
            )
        ]
