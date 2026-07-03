"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (sos_13's prepare spell).

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
        """Needs a creature on the battlefield to target."""
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                ),
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
        on_battlefield = any(
            game.get_battlefield(p).contains(target) for p in game.players
        )
        if not on_battlefield:
            return  # fizzle
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None:
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

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
        self.prepared: bool = False
        self._prepared_copy: Any | None = None

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import (
            EntersBattlefieldTriggeredEvent,
            LeavesBattlefieldTriggeredEvent,
        )
        from engine.game import create_token
        from engine.triggers import TriggerRegistration

        source = self

        def _etb_condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _etb_effect(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            spec = TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
            target = controller.choose_target(list(game.players), spec)
            if target is not None and hasattr(target, "life"):
                token = Creature(
                    name="Inkling",
                    base_power=1,
                    base_toughness=1,
                    subtypes={"Inkling"},
                    keywords=Keyword.FLYING,
                )
                create_token(game, target, token)
            # Then: if an opponent controls more creatures than you …
            def _count(player: Any) -> int:
                return sum(
                    1 for obj in game.get_battlefield(player).get_all()
                    if CardType.CREATURE in getattr(obj, "card_types", set())
                )

            mine = _count(controller)
            if any(
                _count(p) > mine for p in game.players if p is not controller
            ):
                source.become_prepared(game)

        def _leave_condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _leave_effect(game: "GameState") -> None:
            # The exiled prepare-spell copy only exists while the prepared
            # permanent remains on the battlefield (rule 722.3c).
            if source.prepared:
                source.unprepare(game)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_etb_condition,
            effect=_etb_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=LeavesBattlefieldTriggeredEvent,
            condition=_leave_condition,
            effect=_leave_effect,
            source=self,
            controller=controller,
        ))

    # ------------------------------------------------------------------
    # Prepared (rule 722)
    # ------------------------------------------------------------------

    def become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation; create the spell copy in exile."""
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        if self.prepared:
            return  # rule 722.3a — can't gain the designation twice
        controller = self.controller
        if controller is None:
            return
        self.prepared = True
        copy = SwordsToPlowshares(owner=controller, controller=controller)
        self._prepared_copy = copy
        controller.zones[Zone.EXILE].add(copy)

        # The cast copy is a spell copy — it ceases to exist instead of
        # going to a graveyard after it resolves.
        def _condition(game: Any, event: Any) -> bool:
            return event.card is copy

        def _replacement(game: Any, event: Any) -> Any:
            stack_zone = controller.zones[Zone.STACK]
            if stack_zone.contains(copy):
                stack_zone.remove(copy)
            event.prevented = True
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=MoveToGraveyardReplacementEvent,
            source=copy,
            condition=_condition,
            replacement=_replacement,
            controller=controller,
        ))

    def unprepare(self, game: "GameState") -> None:
        """Lose the prepared designation; an uncast copy ceases to exist."""
        self.prepared = False
        copy = self._prepared_copy
        self._prepared_copy = None
        if copy is None:
            return
        controller = self.controller
        if controller is not None:
            exile_zone = controller.zones[Zone.EXILE]
            if exile_zone.contains(copy):
                exile_zone.remove(copy)
                game.replacement_manager.unregister(copy)

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the prepared Swords to Plowshares copy from exile.

        Per rule 722.3c the copy is cast normally — its {W} cost is paid —
        and the permanent is unprepared as the spell becomes cast.
        """
        from engine.casting import CastingError, cast_spell_free

        controller = self.controller
        copy = self._prepared_copy
        if (
            not self.prepared
            or controller is None
            or copy is None
            or not controller.zones[Zone.EXILE].contains(copy)
        ):
            raise CastingError(
                "Cannot cast prepared spell — this creature is not prepared"
            )
        if not controller.mana_pool.pay(copy.mana_cost, spell=copy):
            raise CastingError(
                "Cannot cast prepared spell — cannot pay its mana cost"
            )
        try:
            cast_spell_free(game, controller, copy, Zone.EXILE)
        except CastingError:
            # Refund on failed cast (e.g. no legal target).
            from engine.types import ManaType

            controller.mana_pool.add(ManaType.WHITE, 1)
            raise
        # Designation is lost as the spell becomes cast (rule 601.2i);
        # the copy is on the stack now, so it is not removed.
        self.prepared = False
        self._prepared_copy = None
