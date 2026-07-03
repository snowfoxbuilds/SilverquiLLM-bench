"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creature_count(game: GameState, player: Any) -> int:
    return sum(
        1
        for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (sos_13's prepare spell).

    Exile target creature. Its controller gains life equal to its power.

    When this object is the prepare-spell copy of a prepared Emeritus of
    Truce (``_prepared_source`` set), it is castable from exile only while
    that permanent is prepared and on the battlefield; casting it
    unprepares the permanent, and the copy ceases to exist after it
    resolves (rule 722.3c).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)
        self._prepared_source: Any = None

    def can_cast(self, game: GameState) -> bool:
        source = self._prepared_source
        if source is None:
            return True
        if not getattr(source, "prepared", False):
            return False
        controller = getattr(source, "controller", None)
        return controller is not None and game.get_battlefield(controller).contains(
            source
        )

    def get_targets(self, game: GameState) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_cast(self, game: GameState) -> None:
        source = self._prepared_source
        if source is None:
            return
        # Casting the prepare-spell copy unprepares the permanent.
        source.prepared = False
        source._prepare_copy = None

        # A resolved spell copy ceases to exist instead of going to the
        # graveyard: handle the zone move ourselves and prevent it.
        from engine.events import SpellToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        copy = self

        def _condition(g: Any, event: Any) -> bool:
            return event.card is copy

        def _replacement(g: Any, event: Any) -> Any:
            for p in g.players:
                stack_zone = p.zones[Zone.STACK]
                if stack_zone.contains(copy):
                    stack_zone.remove(copy)
            event.prevented = True
            g.replacement_manager.unregister(copy)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=SpellToGraveyardReplacementEvent,
                source=copy,
                condition=_condition,
                replacement=_replacement,
                controller=self.controller,
            )
        )

    def on_resolve(self, game: GameState) -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        # Confirm the target is still a creature on a battlefield.
        on_battlefield = any(
            game.get_battlefield(p).contains(target) for p in game.players
        )
        if not on_battlefield:
            return
        target_controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if target_controller is not None and power > 0:
            target_controller.life += power
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=target_controller, amount=power)
            )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 —
    Creature — Cat Cleric (prepare spell: Swords to Plowshares, {W}).

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
            "becomes prepared. (While it's prepared, you may cast a copy of "
            "its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False
        self._prepare_copy: Any = None

    def on_resolve(self, game: GameState) -> None:
        """ETB effect — runs at resolution, just before entering the
        battlefield (the engine's convention for "when this enters";
        mirrors fdn_205)."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return
        try:
            chosen = controller.choose_card(
                list(game.players),
                "target player creates a 1/1 white and black Inkling "
                "creature token with flying",
            )
        except Exception:
            chosen = controller
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

        # Then: if an opponent controls more creatures than you, this
        # creature becomes prepared.  While resolving, this creature is
        # still on the stack — count it as yours.
        mine = _creature_count(game, controller)
        if not game.get_battlefield(controller).contains(self):
            mine += 1
        if any(
            _creature_count(game, p) > mine
            for p in game.players
            if p is not controller
        ):
            self._become_prepared(game)

    def register_triggers(self, game: GameState) -> None:
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _leaves_condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _leaves_effect(g: GameState) -> None:
            # The prepare-spell copy exists only while the prepared
            # permanent remains on the battlefield (rule 722.3c).
            copy = getattr(source, "_prepare_copy", None)
            source.prepared = False
            source._prepare_copy = None
            if copy is not None:
                owner = getattr(copy, "owner", None)
                if owner is not None and owner.zones[Zone.EXILE].contains(copy):
                    owner.zones[Zone.EXILE].remove(copy)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_leaves_condition,
                effect=_leaves_effect,
                source=self,
                controller=controller,
            )
        )

    def _become_prepared(self, game: GameState) -> None:
        if self.prepared:
            return  # already has the designation (rule 722.3a)
        controller = self.controller
        if controller is None:
            return
        self.prepared = True
        # Rule 722.3c: as the permanent becomes prepared, its controller
        # creates a copy of the prepare spell in exile; while it remains
        # there its controller may cast it (paying its cost).
        copy = SwordsToPlowshares(owner=controller, controller=controller)
        copy._prepared_source = self
        controller.zones[Zone.EXILE].add(copy)
        self._prepare_copy = copy
