"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _creature_count(player: Any) -> int:
    if player is None:
        return 0
    bf = player.zones[Zone.BATTLEFIELD]
    return sum(
        1
        for o in bf.get_all()
        if CardType.CREATURE in getattr(o, "card_types", set())
    )


def _swords_effect(game: "GameState", target: Any) -> None:
    """Swords to Plowshares: exile target creature; its controller gains life
    equal to that creature's power."""
    if target is None:
        return
    from engine.game import exile as _exile

    controller = getattr(target, "controller", None)
    power = getattr(target, "power", 0)
    _exile(game, target)
    if controller is not None and hasattr(controller, "life"):
        controller.life += power
        if power:
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=power)
            )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the // half of Emeritus of Truce).

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
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        _swords_effect(game, _get_chosen_target(self))


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — Creature — Cat Cleric (3/3).

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    Prepared: while prepared, you may cast a copy of Swords to Plowshares.
    Doing so unprepares it.

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
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        from engine.game import create_token
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "permanent", None) is source

        def _effect(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return

            # "target player" — default to the controller.
            target_player = _get_chosen_target(source)
            if target_player is None or not hasattr(target_player, "life"):
                target_player = controller

            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                base_power=1,
                base_toughness=1,
                keywords=Keyword.FLYING,
            )
            token.colors = {"W", "B"}
            create_token(game, target_player, token)

            # Then if an opponent controls more creatures than you, prepare.
            my_count = _creature_count(controller)
            opp_max = max(
                (_creature_count(p) for p in game.players if p is not controller),
                default=0,
            )
            if opp_max > my_count:
                source.is_prepared = True

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

    # ------------------------------------------------------------------
    # Prepared mechanic
    # ------------------------------------------------------------------

    def make_swords_copy(self, controller: Any = None) -> SwordsToPlowshares:
        """Return a fresh Swords to Plowshares — a copy of this card's spell."""
        ctrl = controller if controller is not None else self.controller
        return SwordsToPlowshares(owner=ctrl, controller=ctrl)

    def cast_prepared_copy(self, game: "GameState", target: Any) -> bool:
        """While prepared, cast a copy of Swords to Plowshares at *target*.

        Returns ``True`` if the copy was cast (which unprepares this card),
        ``False`` if this card was not prepared.
        """
        if not self.is_prepared:
            return False
        copy = self.make_swords_copy(self.controller)
        copy.chosen_targets = [target]
        copy.on_resolve(game)
        self.is_prepared = False
        return True
