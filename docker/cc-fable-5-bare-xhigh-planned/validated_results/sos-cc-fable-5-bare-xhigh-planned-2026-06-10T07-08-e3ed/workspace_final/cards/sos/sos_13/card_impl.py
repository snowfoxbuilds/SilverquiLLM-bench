"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """The prepare spell of Emeritus of Truce (rule 722).

    Swords to Plowshares — {W} — Instant.
    Exile target creature. Its controller gains life equal to its power.

    Only instantiated as the in-exile castable copy created when the
    Emeritus becomes prepared (722.3c); casting it unprepares the source.
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
        # The prepared permanent this copy belongs to (None for a
        # standalone Swords to Plowshares).
        self._prepared_source: Any = None

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_cast(self, game: "GameState") -> None:
        """Casting the prepare-spell copy unprepares its source (722.3c)."""
        prepared_source = self._prepared_source
        if prepared_source is not None and getattr(
            prepared_source, "is_prepared", False
        ):
            # The copy has already left exile (it is on the stack), so
            # unpreparing here only clears the designation.
            prepared_source.unprepare(game)
        self._prepared_source = None

    def on_resolve(self, game: "GameState") -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is not None and CardType.CREATURE in getattr(
            target, "card_types", set()
        ):
            power = getattr(target, "power", 0)
            target_controller = getattr(target, "controller", None)
            exile(game, target)
            if target_controller is not None:
                target_controller.life += power
                game.trigger_manager.fire_event(
                    game,
                    GainsLifeTriggeredEvent(player=target_controller, amount=power),
                )

        # A resolved spell copy ceases to exist (rule 707.10a).
        if getattr(self, "_is_prepare_copy", False):
            self._register_copy_disposal(game)

    def _register_copy_disposal(self, game: "GameState") -> None:
        from engine.events import MoveToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        source = self
        marker = object()

        def _condition(g: Any, event: Any) -> bool:
            return event.card is source

        def _replacement(g: Any, event: Any) -> Any:
            for player in g.players:
                stack_zone = player.zones[Zone.STACK]
                if stack_zone.contains(source):
                    stack_zone.remove(source)
                    break
            event.prevented = True
            g.replacement_manager.unregister(marker)
            return event

        game.replacement_manager.register(
            ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=marker,
                condition=_condition,
                replacement=_replacement,
                controller=getattr(self, "controller", None),
            )
        )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3.

    Creature — Cat Cleric // Instant.
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
            "becomes prepared. (While it's prepared, you may cast a copy of "
            "its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False
        # The castable copy of the prepare spell sitting in exile while
        # this permanent is prepared (722.3c).
        self._prepare_copy: Any = None

    # ------------------------------------------------------------------
    # Preparation (rule 722) — card-local
    # ------------------------------------------------------------------

    def become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation; create the spell copy in exile."""
        if self.is_prepared:
            return  # can't gain the designation twice (722.3a)
        controller = self.controller
        if controller is None:
            return
        self.is_prepared = True
        spell_copy = SwordsToPlowshares(owner=controller, controller=controller)
        spell_copy._prepared_source = self
        spell_copy._is_prepare_copy = True
        controller.zones[Zone.EXILE].add(spell_copy)
        self._prepare_copy = spell_copy

    def unprepare(self, game: "GameState") -> None:
        """Lose the prepared designation; an uncast exile copy ceases to exist."""
        self.is_prepared = False
        spell_copy = self._prepare_copy
        self._prepare_copy = None
        if spell_copy is None:
            return
        owner = getattr(spell_copy, "owner", None)
        if owner is not None and owner.zones[Zone.EXILE].contains(spell_copy):
            owner.zones[Zone.EXILE].remove(spell_copy)

    # ------------------------------------------------------------------
    # Targeting / triggers
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """ETB target: the player who will create the Inkling token."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.game import create_token
        from engine.stack import StackObject
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _etb_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            chosen = getattr(source, "chosen_targets", None)
            target_player = chosen[0] if chosen else None
            if target_player is None or not hasattr(target_player, "life"):
                target_player = ctrl

            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            token.colors = ["W", "B"]
            create_token(game, target_player, token)

            # Then: if an opponent controls more creatures than you,
            # this creature becomes prepared.
            def _creature_count(player: Any) -> int:
                return sum(
                    1
                    for c in player.zones[Zone.BATTLEFIELD].get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                )

            mine = _creature_count(ctrl)
            if any(
                _creature_count(p) > mine
                for p in game.players
                if p is not ctrl
            ):
                source.become_prepared(game)

        def _ltb_condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _ltb_effect(game: "GameState") -> None:
            # The exile copy only persists while the prepared permanent
            # remains on the battlefield (722.3c).
            if source.is_prepared:
                source.unprepare(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_ltb_condition,
                effect=_ltb_effect,
                source=self,
                controller=controller,
            )
        )

        # The engine fires EntersBattlefieldTriggeredEvent *before* calling
        # register_triggers (deliberate ordering), so a permanent's own
        # "when this enters" ability can never fire from that event.
        # register_triggers is only invoked as this card enters the
        # battlefield, so push the ETB ability onto the stack directly.
        game.stack.push(
            StackObject(
                source=self,
                controller=controller,
                on_resolve=_etb_effect,
            )
        )
