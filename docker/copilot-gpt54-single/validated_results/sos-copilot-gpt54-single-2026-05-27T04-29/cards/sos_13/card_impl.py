"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _make_inkling_token() -> Creature:
    """Create the white-and-black Inkling token used by the ETB trigger."""
    return Creature(
        name="Inkling",
        subtypes={"Inkling"},
        base_power=1,
        base_toughness=1,
        keywords=Keyword.FLYING,
        colors={Color.WHITE, Color.BLACK},
        rules_text="Flying",
    )


def _count_creatures(game: "GameState", player: "Player") -> int:
    """Count creatures that player currently controls on the battlefield."""
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    # UNVERIFIED: While it's prepared, you may cast a copy of its spell. Doing so unprepares it. — card spec lacks full spell-face contract and engine has no public prepared-copy casting API

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register the self-only ETB trigger."""
        source = self
        controller = self.controller or game.active_player

        def _condition(game: "GameState", event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _get_targets(game: "GameState", event: EntersBattlefieldTriggeredEvent) -> list[Any]:
            return [
                TargetRequirement(
                    filter_fn=lambda obj: hasattr(obj, "life") and hasattr(obj, "zones"),
                    description="target player",
                    zone=Zone.BATTLEFIELD,
                )
            ]

        def _effect(game: "GameState") -> None:
            from engine.game import create_token

            chosen = getattr(source, "chosen_targets", [])
            target_player = chosen[0] if chosen else None
            if target_player is None or controller is None:
                return

            create_token(game, target_player, _make_inkling_token())

            your_creatures = _count_creatures(game, controller)
            for player in game.players:
                if player is controller:
                    continue
                if _count_creatures(game, player) > your_creatures:
                    source.is_prepared = True
                    return
            source.is_prepared = False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
                get_targets=_get_targets,
            )
        )
