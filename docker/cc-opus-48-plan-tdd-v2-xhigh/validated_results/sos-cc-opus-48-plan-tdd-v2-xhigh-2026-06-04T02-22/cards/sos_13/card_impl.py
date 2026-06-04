"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creature_count(game: "GameState", player: Any) -> int:
    bf = game.get_battlefield(player)
    return sum(
        1 for c in bf.get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Cat Cleric (preparation card).

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    While prepared, you may cast a copy of its prepare spell — Swords to
    Plowshares ({W} Instant): exile target creature; its controller gains
    life equal to its power. Doing so unprepares it.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
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
        # ``register_triggers`` is invoked exactly when a permanent enters the
        # battlefield (after the ETB event has fired), so it doubles as this
        # card's "when this enters" hook.
        self._on_enter(game)

    def _on_enter(self, game: "GameState") -> None:
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return

        target_player = ctrl.choose(
            list(game.players), "Choose target player to create an Inkling"
        )
        if target_player is None:
            target_player = ctrl

        token = Creature(
            name="Inkling", base_power=1, base_toughness=1,
            subtypes={"Inkling"}, keywords=Keyword.FLYING,
        )
        create_token(game, target_player, token)

        my_count = _creature_count(game, ctrl)
        opp_max = max(
            (_creature_count(game, p) for p in game.players if p is not ctrl),
            default=0,
        )
        if opp_max > my_count:
            self.prepared = True

    def get_activated_abilities(self, game: "GameState") -> list[ActivatedAbility]:
        if not getattr(self, "prepared", False):
            return []

        def _cost(game: "GameState", src: Any = self) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            cost = ManaCost.parse("{W}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            ctrl.mana_pool.pay(cost)
            src.prepared = False  # casting the copy unprepares it
            return True

        def _effect(game: "GameState") -> None:
            self._swords_to_plowshares(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Prepared — cast a copy of Swords to Plowshares "
                "({W}): exile target creature; its controller gains life equal "
                "to its power.",
            )
        ]

    def _swords_to_plowshares(self, game: "GameState") -> None:
        from engine.game import exile

        ctrl = self.controller
        if ctrl is None:
            return
        creatures = [
            c
            for pl in game.players
            for c in game.get_battlefield(pl).get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        ]
        if not creatures:
            return
        target = ctrl.choose_card(
            creatures, "Exile target creature (Swords to Plowshares)"
        )
        if target is None:
            return
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None:
            target_controller.life += max(0, power)
