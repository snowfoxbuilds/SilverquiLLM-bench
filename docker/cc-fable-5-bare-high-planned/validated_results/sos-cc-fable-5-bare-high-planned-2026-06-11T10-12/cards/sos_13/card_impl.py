"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creature_count(game: "GameState", player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the prepare spell).

    Exile target creature. Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to "
            "its power.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        return any(
            CardType.CREATURE in getattr(obj, "card_types", set())
            for player in game.players
            for obj in game.get_battlefield(player).get_all()
        )

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        target_controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if target_controller is not None:
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3.

    Creature — Cat Cleric // Instant.
    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # A double-faced card's name is the whole "front // back" string.
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
            "becomes prepared. (While it's prepared, you may cast a copy "
            "of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False
        self._prepare_copy: SwordsToPlowshares | None = None

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Called by the engine exactly when this permanent enters.

        The engine fires the enters-battlefield event *before* registering
        the entering permanent's own triggers, so a self-ETB registration
        would never fire — instead the enter trigger is pushed onto the
        stack directly from this entry hook (card-local workaround).
        """
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.stack import StackObject
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        game.stack.push(
            StackObject(
                source=self,
                controller=controller,
                on_resolve=self._etb_effect,
            )
        )

        # Rule 722.3c: the exiled copy exists only while the prepared
        # permanent remains on the battlefield — unprepare when it leaves.
        def _leave_condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _leave_effect(game: "GameState") -> None:
            source.become_unprepared(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_leave_condition,
                effect=_leave_effect,
                source=self,
                controller=controller,
            )
        )

    def _etb_effect(self, game: "GameState") -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates a 1/1 white-black Inkling with flying.
        target_player = controller.choose(
            list(game.players), "Target player creates an Inkling token"
        )
        if target_player in game.players:
            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            create_token(game, target_player, token)

        # Then if an opponent controls more creatures than you, prepared.
        own = _creature_count(game, controller)
        if any(
            _creature_count(game, p) > own
            for p in game.players
            if p is not controller
        ):
            self.become_prepared(game)

    # ------------------------------------------------------------------
    # Prepared state (rule 722)
    # ------------------------------------------------------------------

    def become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation; create the spell copy in exile."""
        if self.prepared:
            return  # rule 722.3a — can't gain the designation twice
        controller = self.controller
        if controller is None:
            return
        self.prepared = True
        copy = SwordsToPlowshares(owner=self.owner, controller=controller)
        controller.zones[Zone.EXILE].add(copy)
        self._prepare_copy = copy

    def become_unprepared(self, game: "GameState") -> None:
        """Lose the prepared designation; an uncast exile copy ceases."""
        if not self.prepared:
            return
        self.prepared = False
        copy = self._prepare_copy
        self._prepare_copy = None
        if copy is not None:
            for player in game.players:
                exile_zone = player.zones[Zone.EXILE]
                if exile_zone.contains(copy):
                    exile_zone.remove(copy)
                    break

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Controller elects to cast the prepare-spell copy from exile.

        Per rule 722.3c the copy is cast normally (paying its {W} cost);
        the permanent becomes unprepared as the spell is cast.

        Raises:
            CastingError: If not prepared, or the cost/targets are illegal.
        """
        from engine.casting import CastingError, cast_spell_free

        controller = self.controller
        copy = self._prepare_copy
        if not self.prepared or copy is None or controller is None:
            raise CastingError("Not prepared — no spell copy to cast")
        if not controller.mana_pool.can_pay(copy.mana_cost, spell=copy):
            raise CastingError("Cannot pay the prepare spell's mana cost")
        cast_spell_free(game, controller, copy, Zone.EXILE)
        controller.mana_pool.pay(copy.mana_cost, spell=copy)
        copy.mana_spent = copy.mana_cost.cmc  # paid, unlike a true free cast
        # The copy is on the stack now; only the designation is removed.
        self.prepared = False
        self._prepare_copy = None
