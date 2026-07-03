"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
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
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)

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

        chosen = getattr(self, "chosen_targets", None) or [None]
        target = chosen[0]
        if target is None:
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

    The prepare spell is Swords to Plowshares ({W} instant).  Per rule
    722.3c, becoming prepared creates a copy of the prepare spell in exile;
    while prepared, its controller may cast that copy (paying its cost),
    which unprepares this creature.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # A double-faced card's name is the whole "front // back" string.
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        # Front-face cost; the engine's ManaCost cannot represent "// {W}".
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared. (While it's prepared, you may cast a copy of "
            "its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False
        self._prepared_copy: Any = None

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Push the ETB trigger and watch for this creature leaving.

        The engine fires ``EntersBattlefieldTriggeredEvent`` *before*
        registering a permanent's own triggers, so a card's own ETB trigger
        is pushed directly here — this hook runs exactly once per
        battlefield entry.
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

        def _leaves_condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _leaves_effect(game: GameState) -> None:
            # Rule 722.3c: the exiled copy remains only while this permanent
            # is on the battlefield and prepared.
            source._discard_prepared_copy(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_leaves_condition,
                effect=_leaves_effect,
                source=self,
                controller=controller,
            )
        )

    def _etb_effect(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates the Inkling token.
        target_player = controller.choose_card(
            list(game.players),
            "Target player creates a 1/1 white and black Inkling creature "
            "token with flying",
        )
        if target_player in game.players:
            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            create_token(game, target_player, token)

        # Then: if an opponent controls more creatures than you, this
        # creature becomes prepared (token included in the counts).
        def _creature_count(player: Any) -> int:
            return sum(
                1
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        mine = _creature_count(controller)
        if any(
            _creature_count(p) > mine
            for p in game.players
            if p is not controller
        ):
            self._become_prepared(game)

    # ------------------------------------------------------------------
    # Prepared state (rule 722.3)
    # ------------------------------------------------------------------

    def _become_prepared(self, game: GameState) -> None:
        if self.prepared:
            return  # 722.3a — can't gain the designation twice
        controller = self.controller
        if controller is None:
            return
        self.prepared = True
        copy_card = SwordsToPlowshares(owner=controller, controller=controller)
        copy_card.is_copy = True
        controller.zones[Zone.EXILE].add(copy_card)
        self._prepared_copy = copy_card

    def _discard_prepared_copy(self, game: GameState) -> None:
        """Drop the exiled copy and the prepared designation."""
        copy_card = self._prepared_copy
        if copy_card is not None:
            for player in game.players:
                exile_zone = player.zones[Zone.EXILE]
                if exile_zone.contains(copy_card):
                    exile_zone.remove(copy_card)  # the copy ceases to exist
                    break
        self.prepared = False
        self._prepared_copy = None

    def cast_prepared_spell(self, game: GameState) -> None:
        """Cast the exiled Swords to Plowshares copy (pay {W}); unprepares.

        Raises:
            CastingError: If this creature isn't prepared or the cost
                cannot be paid.
        """
        from engine.casting import CastingError, cast_spell_free
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        controller = self.controller
        if not self.prepared or self._prepared_copy is None or controller is None:
            raise CastingError(
                f"Cannot cast prepared spell — {self.name!r} is not prepared"
            )
        copy_card = self._prepared_copy
        cost = copy_card.mana_cost
        if not controller.mana_pool.can_pay(cost, allow_restricted=True):
            raise CastingError(
                "Cannot cast prepared spell — insufficient mana for {W}"
            )

        # A spell copy ceases to exist instead of going to the graveyard
        # (rule 704.5e) — intercept the post-resolution zone move.
        def _repl_condition(game: Any, event: Any) -> bool:
            return event.card is copy_card

        def _replacement(game: Any, event: Any) -> Any:
            for player in game.players:
                stack_zone = player.zones[Zone.STACK]
                if stack_zone.contains(copy_card):
                    stack_zone.remove(copy_card)
                    break
            event.prevented = True
            game.replacement_manager.unregister(copy_card)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=copy_card,
                condition=_repl_condition,
                replacement=_replacement,
                controller=controller,
            )
        )

        controller.mana_pool.pay(cost, allow_restricted=True)
        try:
            cast_spell_free(game, controller, copy_card, Zone.EXILE)
        except CastingError:
            # Refund the cost and withdraw the replacement.
            for mana_type, count in cost.pips.items():
                controller.mana_pool.add(mana_type, count)
            game.replacement_manager.unregister(copy_card)
            raise

        # 722.3c — the permanent loses the designation as the spell is cast.
        self.prepared = False
        self._prepared_copy = None
