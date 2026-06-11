"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class SwordsToPlowshares(Instant):
    """The prepare spell of Emeritus of Truce (rule 722) — {W} Instant.

    Exile target creature. Its controller gains life equal to its power.
    Only ever cast as a copy from exile while the Emeritus is prepared.
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
        """Needs a creature on some battlefield to target."""
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    return True
        return False

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
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return
        power = getattr(target, "power", 0)
        creature_controller = getattr(target, "controller", None)
        exile(game, target)
        if creature_controller is not None:
            creature_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

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
            "becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False
        self._prepared_copy: Any = None

    # ------------------------------------------------------------------
    # ETB — executed directly on battlefield entry (fdn_106 pattern; the
    # engine fires the ETB event before the entering card's own triggers
    # are registered, so a self-ETB TriggerRegistration would never fire).
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.game import create_token
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        # --- ETB effect ---
        chosen_player = controller.choose(
            list(game.players), "Target player creates an Inkling token"
        )
        if chosen_player not in game.players:
            chosen_player = controller
        token = Creature(
            name="Inkling",
            base_power=1,
            base_toughness=1,
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
        )
        create_token(game, chosen_player, token)

        # "Then if an opponent controls more creatures than you…"
        def _creature_count(player: "Player") -> int:
            return sum(
                1
                for c in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
            )

        opponent = (
            game.players[1] if controller is game.players[0] else game.players[0]
        )
        if _creature_count(opponent) > _creature_count(controller):
            self._become_prepared(game, controller)

        # --- Cleanup: the exile copy exists only while this permanent is
        # prepared on the battlefield (rule 722.3c).  Done in the condition
        # so it happens immediately, without a stack round-trip.
        def _cleanup_condition(game: Any, event: Any) -> bool:
            if event.permanent is source:
                source._discard_prepared_copy(game)
            return False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_cleanup_condition,
                effect=lambda g: None,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Prepared (rule 722) — card-local
    # ------------------------------------------------------------------

    def _become_prepared(self, game: "GameState", controller: "Player") -> None:
        if self.is_prepared:
            return  # can't gain the designation twice (722.3a)
        self.is_prepared = True
        # The copy of the prepare spell is created in exile immediately
        # (722.3c) and stays there while this permanent remains prepared.
        spell_copy = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(spell_copy)
        self._prepared_copy = spell_copy

    def _discard_prepared_copy(self, game: "GameState") -> None:
        copy_ref = self._prepared_copy
        if copy_ref is None:
            return
        for player in game.players:
            exile_zone = player.zones[Zone.EXILE]
            if exile_zone.contains(copy_ref):
                exile_zone.remove(copy_ref)  # ceases to exist
        self._prepared_copy = None

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Casting the prepared copy, surfaced as an activatable action.

        The engine has no direct "cast from exile with payment" entry
        point, so the cast is driven through the ability pipeline: the
        cost pays the copy's mana cost {W}, the effect casts it.
        """
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            controller = getattr(src, "controller", None)
            copy_ref = src._prepared_copy
            if (
                controller is None
                or not src.is_prepared
                or copy_ref is None
                or not controller.zones[Zone.EXILE].contains(copy_ref)
            ):
                return False
            if not copy_ref.can_cast(game):
                return False  # no legal target — the copy can't be cast
            cost = copy_ref.mana_cost
            if not controller.mana_pool.can_pay(cost, spell=copy_ref):
                return False
            return controller.mana_pool.pay(cost, spell=copy_ref)

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free
            from engine.events import SpellToGraveyardReplacementEvent
            from engine.replacement_effects import ReplacementEffect

            controller = getattr(source, "controller", None)
            copy_ref = source._prepared_copy
            if controller is None or copy_ref is None:
                return
            try:
                # Mana was paid by the activation cost; this puts the copy
                # on the stack from exile.
                cast_spell_free(game, controller, copy_ref, Zone.EXILE)
            except Exception:
                return  # stays prepared; the copy stays in exile

            # Unprepared at the time the spell becomes cast (722.3c).
            source.is_prepared = False
            source._prepared_copy = None

            # A resolved copy of a card ceases to exist when it leaves the
            # stack (707.10a) — remove it instead of binning it.
            def _repl_condition(game: Any, event: Any) -> bool:
                return event.card is copy_ref

            def _replacement(game: Any, event: Any) -> Any:
                game.replacement_manager.unregister(copy_ref)
                stack_zone = controller.zones[Zone.STACK]
                if stack_zone.contains(copy_ref):
                    stack_zone.remove(copy_ref)
                event.prevented = True
                return event

            game.replacement_manager.register(
                ReplacementEffect(
                    event_type=SpellToGraveyardReplacementEvent,
                    source=copy_ref,
                    condition=_repl_condition,
                    replacement=_replacement,
                    controller=controller,
                )
            )

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "Cast the prepared Swords to Plowshares copy from exile "
                    "by paying {W} (only while prepared; unprepares this "
                    "creature)."
                ),
            )
        ]
