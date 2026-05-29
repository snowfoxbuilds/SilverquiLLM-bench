"""Card implementation for Emeritus of Truce // Swords to Plowshares.

# UNVERIFIED: Inkling token dual-color (white+black) — engine lacks colors field on tokens
# UNVERIFIED: player may decline the prepared ability — DeterministicPlayer lacks 'decline may-ability' script path
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)

    The "spell" is Swords to Plowshares:
    Exile target creature. Its controller gains life equal to its power.
    """

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
            "creatures than you, this creature becomes prepared.\n"
            "(While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        # UNVERIFIED: Inkling token dual-color (white+black) — engine lacks colors field on tokens
        # UNVERIFIED: player may decline the prepared ability — DeterministicPlayer lacks 'decline may-ability' script path
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register the ETB trigger for Inkling token creation and prepared check."""
        source = self
        controller = self.controller

        def _condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _effect(g: "GameState") -> None:
            _resolve_etb(g, source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the prepared Swords to Plowshares ability when prepared."""
        if not self.is_prepared:
            return []

        source = self

        def _stp_effect(game: "GameState") -> None:
            _resolve_swords_to_plowshares(game, source)

        return [
            ActivatedAbility(
                cost=lambda game: None,
                effect=_stp_effect,
                description=(
                    "Prepared — Exile target creature. "
                    "Its controller gains life equal to its power."
                ),
            )
        ]


# ---------------------------------------------------------------------------
# ETB trigger resolution
# ---------------------------------------------------------------------------


def _count_creatures(game: "GameState", player: Any) -> int:
    """Return the number of creatures on *player*'s battlefield."""
    bf = game.get_battlefield(player)
    return sum(
        1
        for obj in bf.get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _resolve_etb(
    game: "GameState",
    source: "EmeritusOfTruceSwordsToPlowshares",
) -> None:
    """Resolve the ETB: create Inkling token for target player, then check prepared."""
    from engine.game import create_token

    chosen = getattr(source, "chosen_targets", None)
    if not chosen:
        return
    target_player = chosen[0]

    # Create a 1/1 Inkling token with Flying for the target player.
    # UNVERIFIED: Inkling token dual-color (white+black) — engine lacks colors field on tokens
    token = Creature(
        name="Inkling",
        base_power=1,
        base_toughness=1,
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        owner=target_player,
        controller=target_player,
    )
    create_token(game, target_player, token)

    # Check if an opponent controls more creatures than this card's controller.
    controller = source.controller
    if controller is None:
        return

    opponents = [p for p in game.players if p is not controller]
    if not opponents:
        return

    my_count = _count_creatures(game, controller)
    opp_max = max(_count_creatures(game, opp) for opp in opponents)

    if opp_max > my_count:
        source.is_prepared = True


# ---------------------------------------------------------------------------
# Swords to Plowshares effect
# ---------------------------------------------------------------------------


def _resolve_swords_to_plowshares(
    game: "GameState",
    source: "EmeritusOfTruceSwordsToPlowshares",
) -> None:
    """Exile target creature; its controller gains life equal to its power. Unprepare."""
    from engine.zones import move_to_zone

    chosen = getattr(source, "chosen_targets", None)
    if not chosen:
        return
    target = chosen[0]

    # Capture power and controller before the zone move.
    power = getattr(target, "power", None)
    if power is None:
        power = getattr(target, "base_power", 0)
    target_controller = getattr(target, "controller", None)

    # Move the creature from the battlefield to exile.
    move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)

    # Its controller gains life equal to its power.
    if target_controller is not None and hasattr(target_controller, "life"):
        target_controller.life += power

    # Unprepare this card.
    source.is_prepared = False
