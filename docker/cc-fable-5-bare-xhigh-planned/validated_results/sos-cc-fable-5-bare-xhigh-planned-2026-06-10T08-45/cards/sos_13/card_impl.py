"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.events import (
    LeavesBattlefieldTriggeredEvent,
    MoveToGraveyardReplacementEvent,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the prepare spell of sos_13).

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

    def can_cast(self, game: GameState) -> bool:
        """Needs a creature to target."""
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    return True
        return False

    def get_targets(self, game: GameState) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

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
        if target_controller is not None:
            target_controller.life += power


def _count_creatures(game: GameState, player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


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
        # A double-faced/preparation card's name is the whole
        # "front // back" string.
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
        self._prepared: bool = False
        self._prepared_copy: SwordsToPlowshares | None = None

    # ------------------------------------------------------------------
    # Prepared state (rule 722)
    # ------------------------------------------------------------------

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    def _become_prepared(self, game: GameState) -> None:
        """Gain the prepared designation; create the prepare-spell copy in
        exile (rule 722.3c)."""
        if self._prepared:
            return
        controller = self.controller
        if controller is None:
            return
        self._prepared = True
        copy = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(copy)
        self._prepared_copy = copy

    def _unprepare(self, game: GameState) -> None:
        """Lose the prepared designation; a copy still in exile ceases."""
        self._prepared = False
        copy = self._prepared_copy
        self._prepared_copy = None
        if copy is not None:
            owner = getattr(copy, "owner", None)
            if owner is not None and owner.zones[Zone.EXILE].contains(copy):
                owner.zones[Zone.EXILE].remove(copy)

    # ------------------------------------------------------------------
    # ETB clause — done in on_resolve, mirroring fdn_205 (the engine never
    # fires a permanent's own EntersBattlefield trigger for its own entry).
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return
        try:
            target_player = controller.choose_card(
                list(game.players), "Target player creates an Inkling token"
            )
        except Exception:
            target_player = controller
        if target_player not in game.players:
            target_player = controller
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, target_player, token)

        # Then if an opponent controls more creatures than you, this
        # creature becomes prepared. This runs while the card is still on
        # the stack (it enters right after), so count it as yours already.
        mine = _count_creatures(game, controller) + 1
        if any(
            _count_creatures(game, p) > mine
            for p in game.players
            if p is not controller
        ):
            self._become_prepared(game)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _leaves_condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _leaves_effect(g: GameState) -> None:
            # The exiled copy only exists while the prepared permanent
            # remains on the battlefield (rule 722.3c).
            source._unprepare(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_leaves_condition,
                effect=_leaves_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Casting the prepared copy
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Expose "cast the prepared copy" as the card's sole printed action.

        Per rule 722.3c the copy is cast normally (paying {W}); casting it
        removes the prepared designation.
        """
        source = self

        def _cost(game: GameState, src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if ctrl is None or not source._prepared:
                return False
            copy = source._prepared_copy
            if copy is None or not ctrl.zones[Zone.EXILE].contains(copy):
                return False
            if not copy.can_cast(game):
                return False
            # Paying for an instant spell, so instant/sorcery-restricted
            # mana is legal here.
            return ctrl.mana_pool.pay(
                ManaCost.parse("{W}"), include_restricted=True
            )

        def _effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free
            from engine.replacement_effects import ReplacementEffect

            ctrl = getattr(source, "controller", None)
            copy = source._prepared_copy
            if ctrl is None or copy is None:
                return

            # A resolved (or countered) spell copy ceases to exist instead
            # of going to a graveyard.
            def _repl_condition(g: Any, ev: Any) -> bool:
                return ev.card is copy

            def _replacement(g: Any, ev: Any) -> Any:
                stack_zone = ctrl.zones[Zone.STACK]
                if stack_zone.contains(copy):
                    stack_zone.remove(copy)
                ev.prevented = True
                g.replacement_manager.unregister(copy)
                return ev

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=copy,
                    condition=_repl_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )
            try:
                cast_spell_free(game, ctrl, copy, Zone.EXILE)
            except CastingError:
                game.replacement_manager.unregister(copy)
                return
            # The permanent unprepares as the copy becomes cast; the copy
            # is on the stack now, so only clear the designation.
            source._prepared = False
            source._prepared_copy = None

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Cast the prepared Swords to Plowshares copy "
                "(pays {W}; unprepares this creature).",
            )
        ]
