"""Card implementation for Emeritus of Truce // Swords to Plowshares (SOS #13)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_creatures(player: Any) -> int:
    """Number of creatures *player* controls on the battlefield."""
    if player is None:
        return 0
    return sum(
        1
        for obj in player.zones[Zone.BATTLEFIELD].get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _all_creatures(game: Any) -> list[Any]:
    """Every creature on the battlefield across all players."""
    creatures: list[Any] = []
    for player in game.players:
        for obj in player.zones[Zone.BATTLEFIELD].get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                creatures.append(obj)
    return creatures


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares (front face) — {1}{W}{W} — 3/3.

    Creature — Cat Cleric.
    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell — Swords to Plowshares: exile target
    creature; its controller gains life equal to its power. Doing so
    unprepares it.)

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
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _etb_condition(game: Any, event: Any) -> bool:
            return getattr(event, "permanent", None) is source

        def _etb_effect(game: Any) -> None:
            from engine.game import create_token

            ctrl = source.controller
            if ctrl is None:
                return

            players = list(game.players)
            target_player = ctrl.choose(players, "target player to create an Inkling")
            if target_player is None or target_player not in players:
                target_player = ctrl

            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            create_token(game, target_player, token)

            # "Then if an opponent controls more creatures than you..."
            mine = _count_creatures(ctrl)
            if any(
                _count_creatures(p) > mine for p in players if p is not ctrl
            ):
                source._prepared = True

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_etb_condition,
                effect=_etb_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        # Swords to Plowshares is only castable while this creature is prepared.
        if not self._prepared:
            return []

        source = self

        def _cost(game: Any) -> bool:
            # ENGINE LIMITATION: "cast a copy of its spell" modelled as a free
            # activated ability (the {W} back-face cost is not charged).
            return True

        def _effect(game: Any) -> None:
            from engine.game import exile

            ctrl = source.controller
            creatures = _all_creatures(game)
            if not creatures:
                return
            target = ctrl.choose_card(creatures, "creature to exile (Swords to Plowshares)")
            if target is None or target not in creatures:
                return
            target_controller = getattr(target, "controller", None)
            power = getattr(target, "power", 0)
            exile(game, target)
            if target_controller is not None:
                target_controller.life += power
            # Casting the copy unprepares this creature.
            source._prepared = False

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Swords to Plowshares: exile target creature; its "
                "controller gains life equal to its power.",
            )
        ]
