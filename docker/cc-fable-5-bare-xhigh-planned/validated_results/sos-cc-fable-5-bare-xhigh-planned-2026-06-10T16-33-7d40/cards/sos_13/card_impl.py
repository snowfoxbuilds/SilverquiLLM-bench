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

    Cast as a copy from exile while the Emeritus is prepared; casting it
    unprepares the Emeritus (rule 722.3c).
    """

    def __init__(self, parent: Any | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to "
            "its power.",
        )
        super().__init__(**kwargs)
        # The prepared permanent this copy belongs to (None for tests that
        # construct a bare Swords).
        self._parent = parent

    def get_targets(self, game: GameState) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def can_cast(self, game: GameState) -> bool:
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    return True
        return False

    def on_cast(self, game: GameState) -> None:
        # Casting the prepared copy unprepares its permanent (722.3c:
        # the designation is lost as the spell becomes cast).
        parent = self._parent
        if parent is not None and getattr(parent, "is_prepared", False):
            parent._unprepare(game)

    def on_resolve(self, game: GameState) -> None:
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        on_battlefield = any(
            game.get_battlefield(p).contains(target) for p in game.players
        )
        if not on_battlefield:
            return
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None and power > 0:
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — Creature — Cat Cleric — 3/3.

    When this creature enters, target player creates a 1/1 white and
    black Inkling creature token with flying. Then if an opponent
    controls more creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so
    unprepares it.)

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
        self.is_prepared: bool = False
        self._prepared_copy: SwordsToPlowshares | None = None

    @property
    def prepared(self) -> bool:
        """Alias for :attr:`is_prepared`."""
        return self.is_prepared

    # ------------------------------------------------------------------
    # Prepared state
    # ------------------------------------------------------------------

    def _prepare(self, game: GameState) -> None:
        """Gain the prepared designation; create the Swords copy in exile.

        Per rule 722.3c the copy exists in exile for as long as this
        permanent is prepared, and its controller may cast it.
        """
        from engine.events import SpellToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        if self.is_prepared:
            return  # 722.3a: can't gain the designation twice
        controller = self.controller
        if controller is None:
            return
        self.is_prepared = True
        copy = SwordsToPlowshares(
            parent=self, owner=controller, controller=controller
        )
        game.get_exile(controller).add(copy)
        self._prepared_copy = copy

        # A resolved copy ceases to exist instead of going to a graveyard.
        def _vanish(g: GameState, event: Any) -> Any:
            stack_zone = controller.zones[Zone.STACK]
            if stack_zone.contains(copy):
                stack_zone.remove(copy)
            event.prevented = True
            g.replacement_manager.unregister(copy)
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=SpellToGraveyardReplacementEvent,
            source=copy,
            condition=lambda g, e: getattr(e, "card", None) is copy,
            replacement=_vanish,
            controller=controller,
        ))

    def _unprepare(self, game: GameState) -> None:
        """Lose the prepared designation; the exiled copy ceases to exist
        unless it has already moved to the stack (it was cast — its
        vanish replacement then cleans up at resolution)."""
        self.is_prepared = False
        copy = self._prepared_copy
        self._prepared_copy = None
        if copy is not None and self.controller is not None:
            exile_zone = game.get_exile(self.controller)
            if exile_zone.contains(copy):
                exile_zone.remove(copy)
                game.replacement_manager.unregister(copy)

    def cast_prepared_spell(self, game: GameState) -> None:
        """Cast the prepared Swords copy from exile, paying its {W} cost.

        Raises:
            CastingError: If not prepared, the cost can't be paid, or
                targeting fails.
        """
        from engine.casting import CastingError, cast_spell_free

        controller = self.controller
        copy = self._prepared_copy
        if not self.is_prepared or copy is None or controller is None:
            raise CastingError("Not prepared — no spell copy to cast")
        cost = copy.mana_cost
        if not controller.mana_pool.can_pay(cost, include_restricted=True):
            raise CastingError(
                "Cannot cast prepared spell — insufficient mana"
            )
        # cast_spell_free performs targeting/legality (its on_cast hook
        # unprepares); the cost is paid here since the prepared copy is
        # cast for its normal cost (rule 722.3c has no free-cast clause).
        cast_spell_free(game, controller, copy, Zone.EXILE)
        controller.mana_pool.pay(cost, include_restricted=True)

    # ------------------------------------------------------------------
    # ETB — in on_resolve, mirroring fdn_205: the engine fires the ETB
    # event before registering the entering permanent's own triggers, so
    # a card's own enter effect runs at spell resolution.
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        def _count_creatures(player: Any) -> int:
            return sum(
                1
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        # Target player creates the Inkling token.
        chosen = controller.choose_target(
            list(game.players), "target player creates an Inkling token"
        )
        if chosen not in game.players:
            chosen = controller
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, chosen, token)

        # Then: prepared if an opponent controls more creatures than you.
        # This runs while the Emeritus is still on the stack — count it as
        # one of your creatures (it enters as this spell resolves).
        mine = _count_creatures(controller)
        if not game.get_battlefield(controller).contains(self):
            mine += 1
        if any(
            _count_creatures(p) > mine
            for p in game.players
            if p is not controller
        ):
            self._prepare(game)

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _ltb_condition(game: GameState, event: Any) -> bool:
            return getattr(event, "permanent", None) is source

        def _ltb_effect(game: GameState) -> None:
            # The exiled copy ceases when the prepared permanent leaves.
            if source.is_prepared:
                source._unprepare(game)

        game.trigger_manager.register(TriggerRegistration(
            event_type=LeavesBattlefieldTriggeredEvent,
            condition=_ltb_condition,
            effect=_ltb_effect,
            source=self,
            controller=self.controller,
        ))
