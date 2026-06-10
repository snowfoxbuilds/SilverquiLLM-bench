"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (Emeritus of Truce's prepare spell).

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

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is not None and CardType.CREATURE in getattr(target, "card_types", set()):
            on_battlefield = any(
                game.get_battlefield(p).contains(target) for p in game.players
            )
            if on_battlefield:
                power = getattr(target, "power", 0)
                target_controller = getattr(target, "controller", None)
                exile(game, target)
                if target_controller is not None:
                    target_controller.life += power

        if getattr(self, "_is_prepared_copy", False):
            # A resolved spell copy ceases to exist — leave the stack zone
            # and land in no other zone.
            controller = self.controller
            if controller is not None:
                stack_zone = controller.zones[Zone.STACK]
                if stack_zone.contains(self):
                    stack_zone.remove(self)


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # A double-faced/preparation card's name is the whole front // back
        # string (rule 722) — the engine keys off the full name.
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
        self._prepared_copy: Any | None = None

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    # ------------------------------------------------------------------
    # Prepared state (rule 722)
    # ------------------------------------------------------------------

    def _become_prepared(self, game: GameState) -> None:
        """Gain the prepared designation: create the Swords copy in exile
        (rule 722.3c); casting that copy unprepares this creature."""
        if self._prepared:
            return  # 722.3a — can't gain the designation twice
        controller = self.controller
        if controller is None:
            return
        self._prepared = True

        spell_copy = SwordsToPlowshares(
            owner=getattr(self, "owner", controller), controller=controller
        )
        spell_copy._is_prepared_copy = True
        controller.zones[Zone.EXILE].add(spell_copy)
        self._prepared_copy = spell_copy

        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _copy_cast_watcher(g: GameState, event: Any) -> bool:
            # Rule 722.3c: the permanent loses the prepared designation at
            # the time the copy becomes cast. Synchronous; never stacks.
            if source._prepared and getattr(event, "card", None) is source._prepared_copy:
                source._prepared = False
                source._prepared_copy = None
            return False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_copy_cast_watcher,
                effect=lambda g: None,
                source=self,
                controller=controller,
            )
        )

    def _unprepare(self, game: GameState) -> None:
        """Lose the prepared designation; the exiled copy ceases to exist."""
        self._prepared = False
        spell_copy = self._prepared_copy
        self._prepared_copy = None
        if spell_copy is not None:
            for player in game.players:
                exile_zone = player.zones[Zone.EXILE]
                if exile_zone.contains(spell_copy):
                    exile_zone.remove(spell_copy)

    # ------------------------------------------------------------------
    # ETB — implemented in on_resolve (fdn_205 convention: the engine fires
    # the ETB event before registering the entering card's own triggers,
    # so a self-ETB trigger never sees its own entry; entries that bypass
    # on_resolve, e.g. reanimation, don't get this effect — engine-wide
    # limitation shared with the FDN cards)
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return
        players = list(game.players)
        try:
            chosen = controller.choose(
                players, "Target player creates a 1/1 white and black "
                "Inkling creature token with flying"
            )
        except Exception:
            chosen = controller
        if chosen not in players:
            chosen = controller
        token = Creature(
            name="Inkling",
            base_power=1,
            base_toughness=1,
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
        )
        create_token(game, chosen, token)

        # Then: if an opponent controls more creatures than you, this
        # creature becomes prepared.
        def _creature_count(p: Any) -> int:
            return sum(
                1
                for obj in game.get_battlefield(p).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        # +1: this creature is entering as the ability resolves and counts
        # toward "creatures you control" (it is still on the stack here).
        mine = _creature_count(controller) + 1
        if any(
            _creature_count(p) > mine for p in players if p is not controller
        ):
            self._become_prepared(game)

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _leave_condition(g: Any, event: Any) -> bool:
            # Losing the battlefield drops the designation and its copy.
            if getattr(event, "permanent", None) is source and source._prepared:
                source._unprepare(g)
            return False

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_leave_condition,
                effect=lambda g: None,
                source=self,
                controller=controller,
            )
        )
