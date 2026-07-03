"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creatures_controlled(game: "GameState", player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _any_creature_on_battlefield(game: "GameState") -> bool:
    return any(
        CardType.CREATURE in getattr(obj, "card_types", set())
        for p in game.players
        for obj in game.get_battlefield(p).get_all()
    )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (sos_13's prepare spell).

    Exile target creature.  Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        return _any_creature_on_battlefield(game)

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
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        on_battlefield = any(
            game.get_battlefield(p).contains(target) for p in game.players
        )
        if not on_battlefield:
            return  # target gone — fizzle
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None and power > 0:
            target_controller.life += power
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=target_controller, amount=power)
            )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3.

    Creature — Cat Cleric // Instant.
    When this creature enters, target player creates a 1/1 white and
    black Inkling creature token with flying.  Then if an opponent
    controls more creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell.  Doing so
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
        self._prepared: bool = False
        self._prepare_copy: SwordsToPlowshares | None = None

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    # ------------------------------------------------------------------
    # Prepared designation (rule 722.3)
    # ------------------------------------------------------------------

    def _become_prepared(self, game: "GameState") -> None:
        if self._prepared:
            return  # can't gain the designation twice (722.3a)
        controller = self.controller
        if controller is None:
            return
        self._prepared = True
        # 722.3c — a copy with the prepare spell's characteristics is
        # created in exile; it stays there while this remains prepared.
        copy = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(copy)
        self._prepare_copy = copy

    def _drop_prepared_copy(self, game: "GameState") -> None:
        """Remove the exiled copy when the designation/permanent goes away."""
        copy = self._prepare_copy
        if copy is None:
            return
        owner = copy.owner
        if owner is not None and owner.zones[Zone.EXILE].contains(copy):
            owner.zones[Zone.EXILE].remove(copy)
        self._prepare_copy = None
        self._prepared = False

    # ------------------------------------------------------------------
    # ETB effect — run at resolution, mirroring fdn_205 (the engine
    # never fires a permanent's own ETB trigger for its own entry).
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return
        target_player = ctrl.choose(
            list(game.players), "Target player creates a 1/1 Inkling token"
        )
        if target_player not in game.players:
            target_player = ctrl
        # ENGINE LIMITATION: token color (white/black) isn't modeled.
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, target_player, token)

        # Then, if an opponent controls more creatures than you...
        # (this creature is still on the stack here but is about to
        # enter, so it counts toward "creatures you control")
        mine = _creatures_controlled(game, ctrl) + 1
        if any(
            p is not ctrl and _creatures_controlled(game, p) > mine
            for p in game.players
        ):
            self._become_prepared(game)

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _ltb_condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _ltb_effect(g: "GameState") -> None:
            # The exiled copy exists only while this stays on the
            # battlefield prepared (722.3c).
            source._drop_prepared_copy(g)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_ltb_condition,
                effect=_ltb_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Casting the prepared copy (the engine's entry point for elective
    # player actions is an activated ability addressed by printed index)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            if not source._prepared or source._prepare_copy is None:
                return False
            ctrl = source.controller
            if ctrl is None:
                return False
            # The prepare spell needs a legal target to be castable.
            if not _any_creature_on_battlefield(game):
                return False
            # Casting the copy pays its normal cost — {W} (no "without
            # paying its mana cost" in the reminder text).
            return ctrl.mana_pool.pay(ManaCost.parse("{W}"))

        def _effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free
            from engine.events import MoveToGraveyardReplacementEvent
            from engine.replacement_effects import ReplacementEffect

            ctrl = source.controller
            copy = source._prepare_copy
            if ctrl is None or copy is None or not source._prepared:
                return
            if not ctrl.zones[Zone.EXILE].contains(copy):
                return

            # 704.5e — a resolved spell copy ceases to exist instead of
            # going to the graveyard.  One-shot replacement that performs
            # the stack-zone removal itself.
            sentinel = object()

            def _repl_condition(g: Any, event: Any) -> bool:
                return event.card is copy

            def _replacement(g: Any, event: Any) -> Any:
                stack_zone = ctrl.zones[Zone.STACK]
                if stack_zone.contains(copy):
                    stack_zone.remove(copy)
                event.prevented = True
                g.replacement_manager.unregister(sentinel)
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=MoveToGraveyardReplacementEvent,
                    source=sentinel,
                    condition=_repl_condition,
                    replacement=_replacement,
                    controller=ctrl,
                )
            )

            try:
                cast_spell_free(game, ctrl, copy, Zone.EXILE)
            except CastingError:
                game.replacement_manager.unregister(sentinel)
                return
            # Casting it removes the prepared designation (601.2i).
            source._prepared = False
            source._prepare_copy = None

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "Cast this creature's prepare spell (Swords to "
                    "Plowshares) from exile — only while prepared; "
                    "doing so unprepares it."
                ),
            )
        ]
