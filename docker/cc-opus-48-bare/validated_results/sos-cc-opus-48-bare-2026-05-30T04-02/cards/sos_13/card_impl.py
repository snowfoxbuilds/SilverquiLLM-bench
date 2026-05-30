"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent, GainsLifeTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _creatures_controlled(player: Any) -> int:
    return sum(
        1
        for obj in player.zones[Zone.BATTLEFIELD].get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if player.zones[Zone.BATTLEFIELD].contains(obj):
            return True
    return False


class _SwordsToPlowshares(Instant):
    """The prepare spell — a copy of which is created in exile while prepared.

    Swords to Plowshares — {W} — Instant.
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
        self.colors: list[str] = ["W"]

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        def _is_target_creature(obj: Any) -> bool:
            return (
                CardType.CREATURE in getattr(obj, "card_types", set())
                and _on_battlefield(game, obj)
            )

        return [
            TargetRequirement(
                filter_fn=_is_target_creature,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        from engine.game import exile

        targets = getattr(self, "chosen_targets", None)
        target = targets[0] if targets else None
        if target is None or not _on_battlefield(game, target):
            # Target left the battlefield before resolution — fizzle.
            self.is_token = True
            return

        # Read power before the creature leaves the battlefield.
        power = getattr(target, "power", 0)
        controller = getattr(target, "controller", None)

        exile(game, target)

        if controller is not None and power > 0:
            controller.life += power
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=controller, amount=power),
            )

        # A cast copy is not a real card: mark it so the token state-based
        # action removes it once it reaches the graveyard after resolution.
        self.is_token = True


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    The prepare spell is Swords to Plowshares ({W} instant).
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
        self.colors: list[str] = ["W"]
        self.prepared: bool = False
        self._stp_copy: _SwordsToPlowshares | None = None

    # ------------------------------------------------------------------
    # ETB trigger — token + conditional prepare
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        source = self

        def _condition(game: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _effect(game: GameState) -> None:
            from engine.game import create_token

            controller = source.controller
            if controller is None:
                return

            target_player = controller.choose(
                list(game.players),
                "Choose target player to create an Inkling token",
            )
            if target_player not in game.players:
                target_player = controller

            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            token.colors = ["W", "B"]
            create_token(game, target_player, token)

            controlled = _creatures_controlled(controller)
            opponent_has_more = any(
                _creatures_controlled(p) > controlled
                for p in game.players
                if p is not controller
            )
            if opponent_has_more:
                source._become_prepared(game)

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
    # Prepared designation
    # ------------------------------------------------------------------

    def _become_prepared(self, game: GameState) -> None:
        """Gain the prepared designation, creating the prepare-spell copy in exile."""
        if self.prepared:
            return  # A permanent can't gain the designation if it already has it.
        controller = self.controller
        if controller is None:
            return
        self.prepared = True
        copy = _SwordsToPlowshares(owner=controller, controller=controller)
        self._stp_copy = copy
        controller.zones[Zone.EXILE].add(copy)

    def can_cast_prepared(self, game: GameState) -> bool:
        """Return True if the prepared copy can currently be cast."""
        if not self.prepared or self._stp_copy is None:
            return False
        controller = self.controller
        if controller is None:
            return False
        if not controller.zones[Zone.EXILE].contains(self._stp_copy):
            return False
        return controller.mana_pool.can_pay(self._stp_copy.mana_cost)

    def cast_prepared(self, game: GameState) -> bool:
        """Cast the prepared copy of Swords to Plowshares from exile.

        Pays the copy's {W} mana cost, removes the prepared designation
        (rule 722.3c), and puts the copy on the stack.  Returns ``True`` on
        success, ``False`` if the copy cannot currently be cast/paid for.
        """
        if not self.can_cast_prepared(game):
            return False
        from engine.casting import cast_spell_free

        controller = self.controller
        copy = self._stp_copy
        assert controller is not None and copy is not None

        controller.mana_pool.pay(copy.mana_cost)
        # The permanent loses prepared as the spell becomes cast.
        self.prepared = False
        self._stp_copy = None
        cast_spell_free(game, controller, copy, Zone.EXILE)
        return True
