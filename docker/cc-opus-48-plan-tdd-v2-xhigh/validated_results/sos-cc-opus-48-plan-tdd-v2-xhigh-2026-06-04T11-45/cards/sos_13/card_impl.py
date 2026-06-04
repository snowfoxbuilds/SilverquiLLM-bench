"""Card implementation for Emeritus of Truce // Swords to Plowshares (SOS #13).

ENGINE LIMITATION: the engine has no split/adventure casting.  The "cast a
copy of its spell" (Swords to Plowshares) clause is modelled as a prepared-only
activated ability that exiles a creature and grants its controller life.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _creature_count(game: "GameState", player: "Player") -> int:
    return sum(
        1
        for o in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(o, "card_types", set())
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 Cat Cleric.

    When this enters, target player creates a 1/1 white and black Inkling
    token with flying.  Then if an opponent controls more creatures than
    you, this becomes prepared.  While prepared you may cast a copy of its
    spell (Swords to Plowshares: exile target creature, its controller
    gains life equal to its power), which unprepares it.

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
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared.",
        )
        super().__init__(**kwargs)
        self._is_prepared: bool = False

    def get_targets(self, game: "GameState") -> list[Any]:
        def _is_player(obj: Any) -> bool:
            return hasattr(obj, "life") and hasattr(obj, "zones")

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
        chosen = getattr(self, "chosen_targets", None) or []
        target_player = chosen[0] if chosen else controller
        if target_player is None:
            target_player = controller
        if target_player is None:
            return

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, target_player, token)

        if controller is None:
            return
        # on_resolve runs before this creature is moved to the battlefield,
        # so count it as one of "your" creatures explicitly.
        my_count = _creature_count(game, controller)
        if self not in game.get_battlefield(controller).get_all():
            my_count += 1
        for opp in game.players:
            if opp is controller:
                continue
            if _creature_count(game, opp) > my_count:
                self._is_prepared = True
                break

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            if not getattr(src, "_is_prepared", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            if not controller.mana_pool.can_pay(ManaCost.parse("{W}")):
                return False
            controller.mana_pool.pay(ManaCost.parse("{W}"))
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import exile

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            target_controller = getattr(target, "controller", None)
            power = getattr(target, "power", 0)
            exile(game, target)
            if target_controller is not None:
                target_controller.life += power
            source._is_prepared = False

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Prepared — {W}: Exile target creature. Its "
                "controller gains life equal to its power.",
            )
        ]
