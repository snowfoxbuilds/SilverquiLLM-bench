"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _make_inkling() -> Creature:
    """A 1/1 white-black Inkling creature token with flying."""
    token = Creature(
        name="Inkling",
        base_power=1,
        base_toughness=1,
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
    )
    token.colors = {"W", "B"}
    return token


def _count_creatures(game: "GameState", player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Creature — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    Back half — Swords to Plowshares — {W} — Instant: Exile target creature.
    Its controller gains life equal to its power.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared.\n"
            "Swords to Plowshares — {W}: Exile target creature. Its "
            "controller gains life equal to its power.",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Handle the self-ETB effect.

        The engine fires ENTERS_BATTLEFIELD before ``register_triggers`` runs,
        so a self-ETB trigger can't catch its own entry — it's handled here on
        resolution instead (the card has not yet reached the battlefield, so
        it is counted explicitly via the ``+ 1`` below).
        """
        from engine.game import create_token

        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return
        target_player = getattr(self, "_token_target", None) or ctrl
        create_token(game, target_player, _make_inkling())

        # "you" includes this creature, which is resolving and about to enter.
        mine = _count_creatures(game, ctrl) + 1
        opp_max = max(
            (_count_creatures(game, p) for p in game.players if p is not ctrl),
            default=0,
        )
        if opp_max > mine:
            self.prepared = True

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _stp_cost(game: "GameState", src: Any) -> bool:
            if not getattr(source, "prepared", False):
                return False
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            cost = ManaCost.parse("{W}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            return ctrl.mana_pool.pay(cost)

        def _stp_effect(game: "GameState") -> None:
            from engine.game import exile

            # Casting the prepared spell unprepares it, regardless of outcome.
            source.prepared = False

            target = getattr(source, "_resolve_target", None)
            if target is None:
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            tgt_controller = getattr(target, "controller", None)
            power = getattr(target, "power", 0)
            exile(game, target)
            if tgt_controller is not None:
                tgt_controller.life += power

        return [
            ActivatedAbility(
                cost=_stp_cost,
                effect=_stp_effect,
                description=(
                    "{W}: (Prepared) Swords to Plowshares — Exile target "
                    "creature. Its controller gains life equal to its power."
                ),
            )
        ]
