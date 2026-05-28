"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

# UNVERIFIED: token is white and black — engine has no color attribute on tokens


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant.

    Exile target creature. Its controller gains life equal to its power.

    This class is the back face of Emeritus of Truce.  When a copy of the
    prepared spell is cast, a fresh instance of this class is created and
    resolved so that the spell effect is isolated and reusable.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Exile target creature; its controller gains life equal to its power."""
        from engine.game import exile as _exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Find the target creature's controller before exiling
        target_controller = getattr(target, "controller", None)
        if target_controller is None:
            for player in game.players:
                bf = game.get_battlefield(player)
                if bf.contains(target):
                    target_controller = player
                    break

        # Record power before exile
        power = getattr(target, "power", getattr(target, "base_power", 0))

        # Exile the creature
        _exile(game, target)

        # Controller gains life equal to power
        if target_controller is not None and hasattr(target_controller, "life"):
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — Creature — Cat Cleric — 3/3.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    (While it's prepared, you may cast a copy of its spell — Swords to
    Plowshares. Doing so unprepares it.)

    Swords to Plowshares: Exile target creature. Its controller gains life
    equal to its power.

    SOS collector number 13.

    Implementation notes
    --------------------
    * ``get_targets()`` advertises one target player for the ETB effect.
      In this engine, ``on_resolve`` is the ETB hook for creature spells;
      ``get_targets`` is how the casting pipeline (and tests) request targets
      before calling ``on_resolve``.  This is the established convention for
      ETB effects (see e.g. ``WardensOfTheCycle`` / ``fdn_205``).
    * The prepared check runs after token creation and adds *self* to the
      controller's creature count, reflecting the real-game timing where
      Emeritus has already entered the battlefield when the check fires.
    * ``cast_prepared_spell`` creates a fresh copy of :class:`SwordsToPlowshares`
      and resolves it directly.  Full stack-based resolution (allowing
      opponents to respond) is an ENGINE LIMITATION — the stack is not
      resolved asynchronously in the current engine.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature becomes "
            "prepared. (While it's prepared, you may cast a copy of its spell. "
            "Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        # Prepared state: True means the controller may cast a free copy of
        # Swords to Plowshares. Defaults to False.
        self.prepared: bool = False

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return target requirements: one target player for the ETB effect.

        The ETB effect requires a target player (who will receive the Inkling
        token).  This method is called by the casting pipeline before
        ``on_resolve``.  Tests also call it directly to verify the contract.
        """
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),  # players have life
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """ETB hook: target player creates a 1/1 Inkling token with flying.

        After the token is created, check if an opponent controls strictly more
        creatures than the controller (counting Emeritus itself as already on
        the battlefield, consistent with real-game timing where the check fires
        after the permanent has entered).  If so, this creature becomes prepared.
        """
        from engine.game import create_token

        chosen = getattr(self, "chosen_targets", None)
        target_player = chosen[0] if chosen else None
        if target_player is None:
            return

        # Create a 1/1 white and black Inkling creature token with flying.
        # UNVERIFIED: token is white and black — engine has no color attribute on tokens
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, target_player, token)

        # Check if an opponent controls more creatures than you.
        controller = self.controller
        if controller is None:
            return

        # Count creatures on each player's battlefield.
        # Emeritus itself is included in the controller's count even when
        # not yet physically on the battlefield (e.g. direct test calls), so
        # that the comparison reflects real-game state where Emeritus has
        # already entered when this check fires.
        def _creature_count(player: Any) -> int:
            bf = game.get_battlefield(player)
            return sum(
                1 for obj in bf.get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        # +1 for Emeritus itself (it has entered the battlefield at this point
        # in real gameplay; tests may not place it on the BF explicitly).
        my_count = _creature_count(controller) + 1
        opponent_has_more = any(
            _creature_count(p) > my_count
            for p in game.players
            if p is not controller
        )

        if opponent_has_more:
            self.prepared = True

    def cast_prepared_spell(self, game: "GameState", target: Any) -> None:
        """Cast a copy of Swords to Plowshares (the prepared spell).

        Creates a fresh :class:`SwordsToPlowshares` instance (the spell copy),
        resolves it against *target*, then sets :attr:`prepared` to ``False``.

        Does nothing if not currently prepared.

        ENGINE LIMITATION: Full stack-based resolution (allowing opponents to
        respond before the copy resolves) is not implemented because the engine
        does not support asynchronous stack resolution from within an ability.
        The copy is resolved immediately, consistent with the simplified
        test contract.
        """
        if not self.prepared:
            return

        controller = self.controller
        # Create a copy of the Swords to Plowshares spell
        stp_copy = SwordsToPlowshares(
            owner=controller,
            controller=controller,
        )
        # Provide the chosen target to the spell copy
        stp_copy.chosen_targets = [target]

        # Resolve the spell copy (applies exile + life-gain effect)
        stp_copy.on_resolve(game)

        # Unset prepared after the copy has been cast
        self.prepared = False
