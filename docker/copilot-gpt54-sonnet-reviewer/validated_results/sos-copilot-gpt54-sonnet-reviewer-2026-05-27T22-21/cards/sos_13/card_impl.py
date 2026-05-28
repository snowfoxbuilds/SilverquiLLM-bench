"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _make_inkling_token() -> Creature:
    """Create the 1/1 white and black Inkling token for Emeritus of Truce."""
    return Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        colors={Color.WHITE, Color.BLACK},
        rules_text="Flying",
        base_power=1,
        base_toughness=1,
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black Inkling creature "
            "token with flying. Then if an opponent controls more creatures than you, this creature "
            "becomes prepared.\n"
            # UNVERIFIED: (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.) — spell-face rules text and public prepared copy-casting API are missing from the current spec/engine surface
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = getattr(self, "controller", None) or getattr(self, "owner", None) or game.active_player

        def _condition(_game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source or event.card is source or event.creature is source

        def _targets(_game: Any, _event: EntersBattlefieldTriggeredEvent) -> list[TargetRequirement]:
            return [
                TargetRequirement(
                    filter_fn=lambda candidate: hasattr(candidate, "life"),
                    description="target player",
                    zone=None,
                )
            ]

        def _effect(game: "GameState") -> None:
            chosen_targets = getattr(source, "chosen_targets", [])
            target_player = chosen_targets[0] if chosen_targets else None
            if target_player is not None and hasattr(target_player, "life"):
                from engine.game import create_token

                create_token(game, target_player, _make_inkling_token())

            if source._an_opponent_controls_more_creatures(game):
                source.prepare()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                target_requirements=_targets,
            )
        )

    def _an_opponent_controls_more_creatures(self, game: "GameState") -> bool:
        controller = getattr(self, "controller", None)
        if controller is None:
            return False

        your_creatures = self._count_creatures(game, controller)
        for player in game.players:
            if player is controller:
                continue
            if self._count_creatures(game, player) > your_creatures:
                return True
        return False

    @staticmethod
    def _count_creatures(game: "GameState", player: "Player") -> int:
        return sum(
            1
            for permanent in game.get_battlefield(player).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )
