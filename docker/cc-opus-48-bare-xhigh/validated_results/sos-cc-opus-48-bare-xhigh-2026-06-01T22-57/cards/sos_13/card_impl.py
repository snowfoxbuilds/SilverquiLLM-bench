"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and not getattr(obj, "card_types", None)


def _count_creatures(player: Any) -> int:
    if player is None:
        return 0
    count = 0
    for obj in player.zones[Zone.BATTLEFIELD].get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            count += 1
    return count


def _all_creatures(game: "GameState") -> list[Any]:
    result: list[Any] = []
    for player in game.players:
        for obj in player.zones[Zone.BATTLEFIELD].get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                result.append(obj)
    return result


def _make_inkling() -> Creature:
    token = Creature(
        name="Inkling",
        base_power=1,
        base_toughness=1,
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
    )
    token.colors = {"W", "B"}
    return token


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    Prepared — while it's prepared, you may cast a copy of its spell (Swords
    to Plowshares: exile target creature, its controller gains life equal to
    its power). Doing so unprepares it.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Cat", "Cleric"}
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.\n"
            "Prepared (While it's prepared, you may cast a copy of its spell. "
            "Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    # ------------------------------------------------------------------
    # Enters-the-battlefield (resolved as the creature spell resolves)
    # ------------------------------------------------------------------
    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        chosen = getattr(self, "chosen_targets", None) or []
        target_player = chosen[0] if chosen and _is_player(chosen[0]) else controller

        create_token(game, target_player, _make_inkling())

        # The entering creature itself counts among "your" creatures even
        # though it is still on the stack at resolution time in this engine.
        your_creatures = _count_creatures(controller) + 1
        opponent_max = max(
            (_count_creatures(p) for p in game.players if p is not controller),
            default=0,
        )
        if opponent_max > your_creatures:
            self._prepared = True

    # ------------------------------------------------------------------
    # Prepared — cast a copy of the spell side (Swords to Plowshares)
    # ------------------------------------------------------------------
    def get_activated_abilities(self) -> list[Any]:
        from engine.card import ActivatedAbility

        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            if not getattr(source, "_prepared", False):
                return False
            controller = source.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost.parse("{W}"))

        def _effect(game: "GameState") -> None:
            from engine.game import exile

            controller = source.controller
            if controller is None:
                return
            # Casting the spell unprepares the creature.
            source._prepared = False

            candidates = _all_creatures(game)
            if not candidates:
                return
            target = controller.choose_card(
                candidates, "Swords to Plowshares — choose target creature to exile"
            )
            if target is None or target not in candidates:
                return
            power = getattr(target, "power", 0)
            target_controller = getattr(target, "controller", None)
            exile(game, target)
            if target_controller is not None:
                target_controller.life += power

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Prepared — {W}: Cast a copy of Swords to Plowshares "
                "(exile target creature; its controller gains life equal to its "
                "power). Unprepares this creature.",
            )
        ]
