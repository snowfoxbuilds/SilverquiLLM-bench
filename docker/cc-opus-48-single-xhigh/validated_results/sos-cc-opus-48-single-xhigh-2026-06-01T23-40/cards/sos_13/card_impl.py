"""Card implementation for Emeritus of Truce // Swords to Plowshares (SOS #13).

This is a *preparation card* (CR 722).  The front face is the creature
**Emeritus of Truce** ({1}{W}{W}, 3/3 Cat Cleric) and the inset "prepare
spell" is **Swords to Plowshares** ({W} instant — exile target creature, its
controller gains life equal to its power).

The engine has no native "Prepared" designation, so this implementation models
the mechanic with a small, additive, card-local surface (mandated by the
coordinator directives):

* ``prepared`` — a boolean attribute (default ``False``); also exposed via the
  read-only ``is_prepared`` alias property.  Set ``True`` during ETB resolution
  only when an opponent controls strictly more creatures than the controller,
  evaluated *after* the Inkling token is created (CR 722.3a).
* ``make_prepare_spell(game)`` — factory returning a castable Swords to
  Plowshares :class:`~engine.card.Instant` whose resolution exiles its chosen
  target creature and grants THAT creature's controller life equal to the
  exiled creature's power.  A no-target resolution is a safe no-op.
* ``cast_prepare_spell(game, target=...)`` — requires ``prepared is True``,
  casts/resolves a fresh copy of the prepare spell "without paying its mana
  cost", then unprepares the permanent (``prepared = False``) per CR 722.3c.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    """Return ``True`` if *obj* is a creature object."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} Instant (the inset prepare spell).

    "Exile target creature. Its controller gains life equal to its power."

    The target is read from :attr:`chosen_targets`.  Resolving with no chosen
    target is a safe no-op (no exile, no life change, no raise).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)
        # Single-letter color identity (the engine has no native colors field).
        self.colors: list[str] = ["W"]

    def on_resolve(self, game: "GameState") -> None:
        """Exile the target creature; its controller gains life equal to power."""
        from engine.game import exile

        targets = getattr(self, "chosen_targets", None) or []
        victim = targets[0] if targets else None
        if victim is None or not _is_creature(victim):
            # No legal target — safe no-op.
            return

        # Snapshot power and controller before the creature leaves play.
        power = getattr(victim, "power", getattr(victim, "base_power", 0)) or 0
        victim_controller = getattr(victim, "controller", None)

        exile(game, victim)

        if victim_controller is not None and hasattr(victim_controller, "life"):
            victim_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Creature — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying.  Then if an opponent controls more
    creatures than you, this creature becomes prepared.  (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13 (preparation-card reference slot, CR 722).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        # The engine has no native colors field — expose the front face's color.
        self.colors: list[str] = ["W"]
        # Preparation designation (CR 722.3a); default unprepared.
        self.prepared: bool = False

    # ------------------------------------------------------------------
    # Prepared designation
    # ------------------------------------------------------------------

    @property
    def is_prepared(self) -> bool:
        """Read-only alias for :attr:`prepared` (CR 722 'prepared' marker)."""
        return self.prepared

    # ------------------------------------------------------------------
    # ETB trigger: token creation + becomes-prepared comparison
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the enters-the-battlefield triggered ability."""
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return getattr(event, "permanent", None) is source

        def _effect(game: "GameState") -> None:
            self._resolve_etb(game)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _resolve_etb(self, game: "GameState") -> None:
        """Resolve the ETB: create the Inkling token, then check prepared.

        The token is created BEFORE the "more creatures than you" comparison,
        so a token given to an opponent counts toward that opponent's total.
        """
        from engine.game import create_token

        controller = getattr(self, "controller", None)
        if controller is None:
            return

        # 1. Target player creates a 1/1 white-and-black Inkling with flying.
        targets = getattr(self, "chosen_targets", None) or []
        target_player = targets[0] if targets else controller

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        token.colors = ["W", "B"]
        create_token(game, target_player, token)

        # 2. Then if an opponent controls more creatures than you, prepare.
        if self._opponent_controls_more_creatures(game, controller):
            self.prepared = True

    @staticmethod
    def _creature_count(game: "GameState", player: Any) -> int:
        """Number of creatures *player* controls on the battlefield."""
        return sum(
            1
            for obj in game.get_battlefield(player).get_all()
            if _is_creature(obj)
        )

    def _opponent_controls_more_creatures(
        self, game: "GameState", controller: Any
    ) -> bool:
        """Return ``True`` iff some opponent controls strictly more creatures.

        Standard MTG counting (CR 722.3a, evaluated when the ETB resolves): the
        entering Emeritus is on the battlefield, so it counts toward "you" (the
        controller), as does the just-created Inkling token if it was given to
        you.  Tokens count for whoever controls them.  Each opponent's count
        includes every creature they control (including a token granted to
        them).  "More than" is strict ``>``.
        """
        my_count = self._creature_count(game, controller)
        for player in game.players:
            if player is controller:
                continue
            if self._creature_count(game, player) > my_count:
                return True
        return False

    # ------------------------------------------------------------------
    # Prepare spell — Swords to Plowshares
    # ------------------------------------------------------------------

    def make_prepare_spell(self, game: "GameState") -> SwordsToPlowshares:
        """Return a castable copy of the Swords to Plowshares prepare spell.

        The copy's controller/owner default to this permanent's controller
        (CR 722.3c: the prepared permanent's controller may cast the copy).
        """
        controller = getattr(self, "controller", None)
        owner = getattr(self, "owner", None) or controller
        spell = SwordsToPlowshares(owner=owner, controller=controller)
        return spell

    # ------------------------------------------------------------------
    # Cast-while-prepared + unprepare (CR 722.3c)
    # ------------------------------------------------------------------

    def cast_prepare_spell(
        self,
        game: "GameState",
        target: Any | None = None,
    ) -> SwordsToPlowshares:
        """Cast a copy of the prepare spell (free), then unprepare.

        Requires :attr:`prepared` to be ``True`` (raises otherwise).  Resolves
        a fresh Swords to Plowshares copy against *target* (read from
        ``chosen_targets`` if not given) "without paying its mana cost", then
        clears the prepared designation (CR 722.3c).

        Returns the resolved prepare-spell object.
        """
        if not self.prepared:
            raise ValueError(
                "Emeritus of Truce is not prepared; cannot cast its prepare spell."
            )

        spell = self.make_prepare_spell(game)
        if target is not None:
            spell.chosen_targets = [target]

        # The copy is cast "without paying its mana cost"; resolve it directly.
        spell.on_resolve(game)

        # Casting the prepare spell unprepares the permanent (CR 722.3c).
        self.prepared = False
        return spell
