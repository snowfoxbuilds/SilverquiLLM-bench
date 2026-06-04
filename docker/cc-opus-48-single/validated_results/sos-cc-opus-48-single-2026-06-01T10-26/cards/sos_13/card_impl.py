"""Card implementation for Emeritus of Truce // Swords to Plowshares.

Front face: **Emeritus of Truce** — ``{1}{W}{W}`` white Creature — Cat Cleric,
3/3, with the SOS-specific **Prepared** keyword.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

The prepare spell (inset face) is **Swords to Plowshares** — a ``{W}`` instant:

    Exile target creature. Its controller gains life equal to its power.

Testable contract exposed by this implementation
------------------------------------------------
* ``card.is_prepared`` — bool, starts ``False``; becomes ``True`` only when an
  opponent controls strictly more creatures than the controller after the ETB.
  (The Prepared mechanic is surfaced via this attribute and the rules text
  rather than a ``Keyword`` enum member, since the engine's keyword set is
  pinned by an authoritative regression test.)
* ``card.prepare_spell`` (also aliased as ``prepared_spell`` / ``other_face``)
  — a :class:`SwordsToPlowshares` instance (name ``"Swords to Plowshares"``,
  cost ``{W}``).
* ``card.register_triggers(game)`` registers a self-only ETB trigger watching
  :class:`EntersBattlefieldTriggeredEvent`. Resolving it creates a 1/1 flying
  white+black Inkling token for the chosen target player and conditionally sets
  ``is_prepared``.
* Casting the prepared copy is driven by
  :func:`engine.casting.cast_prepared_spell` (or the convenience method
  :meth:`EmeritusOfTruceSwordsToPlowshares.cast_prepare_copy`): it puts a copy
  of Swords to Plowshares on the stack and clears ``is_prepared``. Resolving the
  copy exiles the target creature and gives its controller life equal to its
  power.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Color, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _self_etb_condition(source: Any):
    """Return a condition callable matching only when *source* enters."""

    def _condition(game: Any, event: Any) -> bool:
        return getattr(event, "permanent", None) is source

    return _condition


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} instant (the prepare spell / inset face).

    Exile target creature. Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("colors", {Color.WHITE})
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: GameState) -> list[Any]:
        """Target a creature on the battlefield."""
        from engine.types import TargetRequirement

        def _is_creature(obj: Any) -> bool:
            return CardType.CREATURE in getattr(obj, "card_types", set())

        return [
            TargetRequirement(
                filter_fn=_is_creature,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Exile the target creature; its controller gains life = its power."""
        from engine.game import exile

        targets = getattr(self, "chosen_targets", None) or []
        target = targets[0] if targets else None
        if target is None:
            return

        # Capture power and controller before the creature leaves the battlefield.
        power = getattr(target, "power", getattr(target, "base_power", 0))
        target_controller = getattr(target, "controller", None)

        exile(game, target)

        if target_controller is not None and hasattr(target_controller, "life") and power > 0:
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — SOS 13.

    {1}{W}{W} white Creature — Cat Cleric, 3/3, Prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("colors", {Color.WHITE})
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        # Prepared designation — starts cleared; only the ETB conditional sets it.
        self.is_prepared: bool = False
        # The inset prepare spell (Swords to Plowshares).
        self.prepare_spell: SwordsToPlowshares = SwordsToPlowshares(
            owner=self.owner, controller=self.controller
        )

    # Aliases so test code can discover the prepare spell under several names.
    @property
    def prepared_spell(self) -> SwordsToPlowshares:
        return self.prepare_spell

    @property
    def other_face(self) -> SwordsToPlowshares:
        return self.prepare_spell

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _effect(game: GameState) -> None:
            self._etb_effect(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition(self),
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _etb_effect(self, game: GameState) -> None:
        """ETB: target player creates the Inkling, then conditional prepare."""
        from engine.game import create_token

        controller = getattr(self, "controller", None) or game.active_player

        # "target player creates ..." — ask the controller to choose a player.
        target_player = self._choose_target_player(game, controller)

        # Create a 1/1 white and black Inkling creature token with flying.
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
            colors={Color.WHITE, Color.BLACK},
            owner=target_player,
            controller=target_player,
        )
        create_token(game, target_player, token)

        # "Then if an opponent controls more creatures than you, this creature
        # becomes prepared." Strict comparison; this creature counts for "you".
        if self._opponent_controls_more_creatures(game, controller):
            self.is_prepared = True

    def _choose_target_player(self, game: GameState, controller: Any) -> Any:
        """Choose the target player for the token (defaults to controller)."""
        from engine.types import TargetRequirement

        chooser = controller
        choose_target = getattr(chooser, "choose_target", None)
        if choose_target is None:
            return controller
        spec = TargetRequirement(
            filter_fn=lambda obj: hasattr(obj, "life"),
            description="target player",
            zone=Zone.BATTLEFIELD,
        )
        try:
            chosen = chooser.choose_target(list(game.players), spec)
        except Exception:
            return controller
        # Only honour the choice if it is actually a player object.
        if chosen in game.players:
            return chosen
        return controller

    @staticmethod
    def _count_creatures(game: GameState, player: Any) -> int:
        bf = game.get_battlefield(player)
        return sum(
            1
            for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

    def _opponent_controls_more_creatures(self, game: GameState, controller: Any) -> bool:
        mine = self._count_creatures(game, controller)
        for opp in game.players:
            if opp is controller:
                continue
            if self._count_creatures(game, opp) > mine:
                return True
        return False

    # ------------------------------------------------------------------
    # Prepared cast loop
    # ------------------------------------------------------------------

    def cast_prepare_copy(self, game: GameState, targets: list[Any] | None = None):
        """Cast a copy of the prepare spell while prepared (convenience wrapper).

        Delegates to :func:`engine.casting.cast_prepared_spell`. Casting clears
        ``is_prepared``. Returns the resulting :class:`StackObject` (or ``None``
        if not prepared).
        """
        from engine.casting import cast_prepared_spell

        return cast_prepared_spell(game, self, targets=targets)
