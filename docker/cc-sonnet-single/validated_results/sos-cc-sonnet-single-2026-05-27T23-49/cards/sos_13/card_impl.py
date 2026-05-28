"""Card implementation for Emeritus of Truce // Swords to Plowshares (SOS #13).

Emeritus of Truce — {1}{W}{W} — 3/3 — Cat Cleric — Creature

When this creature enters, target player creates a 1/1 white and black
Inkling creature token with flying.  Then if an opponent controls more
creatures than you, this creature becomes prepared.

Prepared mechanic:
  While prepared, you may cast a copy of its spell (Swords to Plowshares).
  Doing so unprepares it.

Swords to Plowshares — {W} — Instant
  Exile target creature. Its controller gains life equal to its power.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# ---------------------------------------------------------------------------
# Swords to Plowshares — the spell side
# ---------------------------------------------------------------------------

class _SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant.

    Exile target creature. Its controller gains life equal to its power.
    This is the spell side of Emeritus of Truce.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Inkling token factory
# ---------------------------------------------------------------------------

def _make_inkling_token(owner: Any, controller: Any) -> Creature:
    """Create a 1/1 white and black Inkling creature token with flying."""
    token = Creature(
        name="Inkling",
        mana_cost=ManaCost(),
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
        owner=owner,
        controller=controller,
    )
    token.is_token = True
    # Colors: white and black
    token.colors = {"W", "B"}
    return token


# ---------------------------------------------------------------------------
# Main card class
# ---------------------------------------------------------------------------

class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    ETB: target player creates a 1/1 white and black Inkling creature token
    with flying.  Then if an opponent controls more creatures than you, this
    creature becomes prepared.

    Prepared: you may cast a copy of Swords to Plowshares (exile target
    creature; its controller gains life equal to its power).  Doing so
    unprepares this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
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

        # Prepared state
        self.is_prepared: bool = False

        # Spell side — Swords to Plowshares
        self.spell_side: _SwordsToPlowshares = _SwordsToPlowshares()

    # ------------------------------------------------------------------
    # Targeting API
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Return a targeting requirement: a player to receive the Inkling token."""
        # The target is a player (any player)
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj in game.players,
                description="target player",
                zone=Zone.BATTLEFIELD,  # zone is conceptually 'any' for players
            )
        ]

    # ------------------------------------------------------------------
    # ETB resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """ETB effect: create Inkling token for target player; check prepared."""
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_player = chosen[0]

        # Step 1: Target player creates a 1/1 white and black Inkling token
        # with flying.
        from engine.game import create_token
        token = _make_inkling_token(owner=target_player, controller=target_player)
        create_token(game, target_player, token)

        # Step 2: If an opponent controls more creatures than you, become prepared.
        controller = getattr(self, "controller", None)
        if controller is None:
            return

        my_creature_count = _count_creatures_controlled_by(game, controller)
        opponent_max = _max_opponent_creature_count(game, controller)

        if opponent_max > my_creature_count:
            self.is_prepared = True

    # ------------------------------------------------------------------
    # Trigger registration
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the ETB trigger."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: "GameState", event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _effect(g: "GameState") -> None:
            source.on_resolve(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Prepared mechanic: cast spell copy
    # ------------------------------------------------------------------

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Swords to Plowshares if this creature is prepared.

        Casting the copy requires a legal target (a creature on the battlefield).
        If no target exists, the spell cannot be cast and the creature remains
        prepared.  Only unprepares after a valid target is found and the effect
        can proceed.
        """
        if not self.is_prepared:
            return

        # Find a target creature on any battlefield first.
        # If no legal target exists, the spell cannot be cast; creature stays prepared.
        target = _find_any_creature(game)
        if target is None:
            return

        # A legal target exists — the spell copy is cast.  Unprepare the creature.
        self.is_prepared = False

        # Exile the target creature and give its controller life = power.
        _exile_creature_give_life(game, target)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _count_creatures_controlled_by(game: Any, player: Any) -> int:
    """Return the number of creatures player controls on the battlefield."""
    bf = game.get_battlefield(player)
    return sum(
        1 for obj in bf.get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _max_opponent_creature_count(game: Any, player: Any) -> int:
    """Return the maximum creature count among any single opponent."""
    max_count = 0
    for p in game.players:
        if p is player:
            continue
        count = _count_creatures_controlled_by(game, p)
        if count > max_count:
            max_count = count
    return max_count


def _find_any_creature(game: Any) -> Any:
    """Return the first creature found on any player's battlefield, or None."""
    for player in game.players:
        bf = game.get_battlefield(player)
        for obj in bf.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                return obj
    return None


def _exile_creature_give_life(game: Any, creature: Any) -> None:
    """Exile *creature* and grant its controller life equal to its power."""
    from engine.game import exile

    power = getattr(creature, "power", 0)
    ctrl = getattr(creature, "controller", None)

    exile(game, creature)

    if ctrl is not None and power > 0:
        ctrl.life += power
