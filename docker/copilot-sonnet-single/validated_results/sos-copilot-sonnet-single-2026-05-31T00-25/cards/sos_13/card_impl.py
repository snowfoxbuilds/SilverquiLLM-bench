"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant.

    Exile target creature. Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return
        target = targets[0]
        if not isinstance(target, Creature):
            return

        power = getattr(target, "power", None)
        if power is None:
            power = getattr(target, "base_power", 0)

        creature_controller = getattr(target, "controller", None)

        exile(game, target)

        if creature_controller is not None and power > 0:
            creature_controller.life += power


class EmeritusOfTruce(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 Creature — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    Prepared: You may cast a copy of Swords to Plowshares.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register ETB trigger to create Inkling token and possibly become prepared."""
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        def condition(g: "GameState", event: Any) -> bool:
            return event.permanent is self

        def effect(g: "GameState") -> None:
            _etb_effect(g, self)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=condition,
                effect=effect,
                source=self,
                controller=self.controller,
            )
        )

    def get_activated_abilities(self) -> list:
        """If prepared, expose the Swords to Plowshares ability."""
        from engine.card import ActivatedAbility

        abilities = []

        def cost_fn(game: "GameState") -> bool:
            return self.prepared

        def effect_fn(game: "GameState") -> None:
            _cast_swords_copy(game, self)

        if self.prepared:
            abilities.append(
                ActivatedAbility(
                    cost=cost_fn,
                    effect=effect_fn,
                    description="Cast a copy of Swords to Plowshares (prepared).",
                )
            )
        return abilities


# ---------------------------------------------------------------------------
# Alias so tests can import either name
# ---------------------------------------------------------------------------
EmeritusOfTruceSwordsToPlowshares = EmeritusOfTruce


def _etb_effect(game: "GameState", source: EmeritusOfTruce) -> None:
    """Create 1/1 Inkling token, then check prepared condition."""
    from engine.game import create_token

    controller = source.controller
    if controller is None:
        return

    # Target player (default to controller if no targeting in test context)
    target_player = controller

    # Snapshot creature counts BEFORE creating the token (the "then" clause
    # checks whether an opponent controls more — evaluated at the moment of
    # the check, but the token creation and comparison are sequential steps;
    # for correct game-state semantics we snapshot before adding the token so
    # the Inkling itself does not influence the comparison).
    my_creatures_before = _count_creatures(game, controller)
    opponent_max = max(
        (_count_creatures(game, opp) for opp in game.players if opp is not controller),
        default=0,
    )

    # Create 1/1 white and black Inkling with flying
    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        base_power=1,
        base_toughness=1,
        keywords=Keyword.FLYING,
    )
    create_token(game, target_player, token)

    # Become prepared if an opponent had more creatures than we did
    if opponent_max > my_creatures_before:
        source.prepared = True


def _count_creatures(game: "GameState", player: Any) -> int:
    """Count creatures on the battlefield for player."""
    bf = game.get_battlefield(player)
    return sum(1 for obj in bf.get_all() if isinstance(obj, Creature))


def _cast_swords_copy(game: "GameState", source: EmeritusOfTruce) -> None:
    """Create and resolve a copy of Swords to Plowshares, then unprepare."""
    source.prepared = False
    controller = source.controller
    if controller is None:
        return

    # Find a target creature on battlefield (any opponent's creature first)
    target = None
    for player in game.players:
        if player is controller:
            continue
        bf = game.get_battlefield(player)
        for obj in bf.get_all():
            if isinstance(obj, Creature):
                target = obj
                break
        if target is not None:
            break

    if target is None:
        return

    from engine.game import exile
    power = getattr(target, "power", None)
    if power is None:
        power = getattr(target, "base_power", 0)
    creature_controller = getattr(target, "controller", None)
    exile(game, target)
    if creature_controller is not None and power > 0:
        creature_controller.life += power
