"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — Creature — Cat Cleric — 3/3.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            (
                "When this creature enters, target player creates a 1/1 white "
                "and black Inkling creature token with flying. Then if an "
                "opponent controls more creatures than you, this creature "
                "becomes prepared."
            ),
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False
        self.chosen_targets: list[Any] = []

    def _count_creatures(self, game: "GameState", player: Any) -> int:
        """Count creatures on the battlefield controlled by *player*."""
        bf = game.get_battlefield(player)
        return sum(
            1 for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the ETB triggered ability."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _effect(game: "GameState") -> None:
            from engine.game import create_token

            targets = getattr(source, "chosen_targets", [])
            if not targets:
                return

            target_player = targets[0]

            # Create the 1/1 white and black Inkling creature token with flying
            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                base_power=1,
                base_toughness=1,
                keywords=Keyword.FLYING,
                colors={Color.WHITE, Color.BLACK},
            )
            token.is_token = True
            create_token(game, target_player, token)

            # UNVERIFIED: "while prepared, may cast a copy of the spell (Swords to Plowshares)" —
            #   prepared-spell copy-cast pipeline not in engine test infrastructure
            # UNVERIFIED: "casting the prepared spell unprepares it (is_prepared -> False)" —
            #   same dependency on prepared-spell casting pipeline

            # Check if an opponent controls strictly more creatures than the controller
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            ctrl_count = source._count_creatures(game, ctrl)
            opp_has_more = False
            for player in game.players:
                if player is ctrl:
                    continue
                opp_count = source._count_creatures(game, player)
                if opp_count > ctrl_count:
                    opp_has_more = True
                    break

            source.is_prepared = opp_has_more

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
