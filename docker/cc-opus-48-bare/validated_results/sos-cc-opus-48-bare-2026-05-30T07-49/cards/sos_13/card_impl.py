"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _count_creatures(game: Any, player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _all_creatures(game: Any) -> list:
    creatures: list = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                creatures.append(obj)
    return creatures


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} // {W}.

    Front face: Emeritus of Truce, a 3/3 Cat Cleric.  When it enters, target
    player creates a 1/1 white and black Inkling creature token with flying.
    Then if an opponent controls more creatures than you, this creature
    becomes *prepared*.

    While it's prepared you may cast a copy of its spell — Swords to
    Plowshares ({W}: exile target creature; its controller gains life equal to
    its power).  Doing so unprepares it.

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
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        # "Prepared" is a set-specific keyword counter, not an engine keyword;
        # tracked here rather than in ``keywords`` so engine handlers ignore it.
        self._prepared: bool = False

    # ------------------------------------------------------------------
    # Enters-the-battlefield trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            return getattr(event, "permanent", None) is source

        def _effect(g: "GameState") -> None:
            source._etb(g)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _etb(self, game: "GameState") -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        target_player = controller.choose(
            list(game.players), "target player to create an Inkling token"
        )
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

        # "Then if an opponent controls more creatures than you ..."
        mine = _count_creatures(game, controller)
        for opponent in game.players:
            if opponent is controller:
                continue
            if _count_creatures(game, opponent) > mine:
                self._prepared = True
                break

    # ------------------------------------------------------------------
    # Prepared: cast a copy of Swords to Plowshares
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if not getattr(src, "_prepared", False):
                return False
            if not _is_on_battlefield(game, src):
                return False
            cost = ManaCost.parse("{W}")
            if not controller.mana_pool.can_pay(cost):
                return False
            if not _all_creatures(game):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _effect(game: Any) -> None:
            source._cast_stp(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "Prepared — {W}: Exile target creature. Its controller "
                    "gains life equal to its power. This unprepares this "
                    "creature."
                ),
            )
        ]

    def _cast_stp(self, game: "GameState") -> None:
        from engine.game import exile

        controller = self.controller
        if controller is None:
            return

        candidates = _all_creatures(game)
        if not candidates:
            return

        target = controller.choose_card(candidates, "creature to exile")
        if target is None or CardType.CREATURE not in getattr(
            target, "card_types", set()
        ):
            return

        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None:
            target_controller.life += power

        # "Doing so unprepares it."
        self._prepared = False
