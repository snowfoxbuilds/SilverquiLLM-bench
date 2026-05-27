"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.game import create_token, exile
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone


if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowsharesPreparedSpell(Instant):
    """Prepared spell half for Emeritus of Truce."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)
        self.colors = {"W"}

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Exile target creature and grant its controller life equal to its power."""
        chosen = getattr(self, "chosen_targets", [])
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        controller = getattr(target, "controller", None)
        if controller is not None and hasattr(controller, "life"):
            controller.life += getattr(target, "power", getattr(target, "base_power", 0))
        exile(game, target)


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.colors = {"W"}
        self.prepared_spell_factory = SwordsToPlowsharesPreparedSpell
        self.prepared_spell_name = "Swords to Plowshares"

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Expose the ETB target player through the spell for the current engine."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life")
                and CardType.CREATURE not in getattr(obj, "card_types", set()),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    @staticmethod
    def _count_creatures(game: "GameState", player: Any) -> int:
        """Count creatures a player currently controls on the battlefield."""
        return sum(
            1
            for permanent in game.get_battlefield(player).get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
        )

    @staticmethod
    def _make_inkling() -> Creature:
        """Create the 1/1 flying Inkling token."""
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            base_power=1,
            base_toughness=1,
            keywords=Keyword.FLYING,
        )
        token.colors = {"W", "B"}
        return token

    def on_resolve(self, game: "GameState") -> None:
        """Create the targeted Inkling and prepare if an opponent controls more creatures."""
        chosen = getattr(self, "chosen_targets", [])
        target_player = chosen[0] if chosen else None
        controller = self.controller
        if target_player is None or controller is None:
            self.unprepare()
            return

        create_token(game, target_player, self._make_inkling())

        your_creatures = self._count_creatures(game, controller)
        if not any(self is permanent for permanent in game.get_battlefield(controller).get_all()):
            your_creatures += 1

        if any(
            opponent is not controller
            and self._count_creatures(game, opponent) > your_creatures
            for opponent in game.players
        ):
            self.prepare()
        else:
            self.unprepare()
