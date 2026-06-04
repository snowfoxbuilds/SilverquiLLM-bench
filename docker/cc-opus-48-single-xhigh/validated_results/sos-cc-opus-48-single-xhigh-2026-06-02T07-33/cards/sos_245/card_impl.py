"""Card implementation for Witherbloom, the Balancer (SOS 245)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _count_creatures_controlled(game: Any, controller: Any) -> int:
    """Return how many creatures *controller* controls (on their battlefield)."""
    if controller is None:
        return 0
    count = 0
    for card in game.get_battlefield(controller).get_all():
        if CardType.CREATURE in getattr(card, "card_types", set()):
            count += 1
    return count


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon.

    Affinity for creatures (this spell costs {1} less to cast for each creature
    you control.)
    Flying, deathtouch.
    Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    #: "Affinity" is a printed keyword label, NOT an evergreen
    #: ``engine.types.Keyword`` enum member (that enum is frozen at 16 members),
    #: so it is recorded as a printed-keyword label below.
    AFFINITY_LABEL = "Affinity"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Dragon", "Elder"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)
        # Explicit colour identity (B+G) so the colour is stable even when the
        # cost is unavailable; the cost pips already encode it.
        self.colors: list[Color] = [Color.BLACK, Color.GREEN]
        # Printed-keyword label surface — Affinity is a printed keyword, not an
        # evergreen ``Keyword`` enum member.
        self.printed_keywords: list[str] = [self.AFFINITY_LABEL]

    # ------------------------------------------------------------------
    # Witherbloom's OWN affinity for creatures — cost reduction.
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce the generic cost by {1} per creature its controller controls.

        Affinity for creatures: only creatures the CONTROLLER controls count
        (an opponent's creatures do not; non-creature permanents do not).  The
        engine clamps the final value so generic mana never goes below 0 (see
        ``engine.casting.get_cost_reduction``).  While Witherbloom is on the
        stack being cast it is not on the battlefield, so it does not count
        itself.
        """
        return _count_creatures_controlled(game, self.controller)

    # ------------------------------------------------------------------
    # Granted affinity for creatures — queryable grant surface.
    # ------------------------------------------------------------------

    def has_affinity_for_creatures(self, game: "GameState", spell: Any) -> bool:
        """Return ``True`` if this card grants affinity for creatures to *spell*.

        Witherbloom grants affinity for creatures to every instant and sorcery
        spell *its controller casts*.  This is the queryable grant surface the
        tests probe: it returns ``True`` only when

        * Witherbloom is on the battlefield,
        * *spell* is an instant or a sorcery, and
        * *spell* is controlled by / in the hand of Witherbloom's controller,

        and ``False`` otherwise (creatures, an opponent's spell, off-battlefield).
        """
        from engine.affinity import is_instant_or_sorcery

        controller = self.controller
        if controller is None:
            return False
        if not _is_on_battlefield(game, self):
            return False
        if not is_instant_or_sorcery(spell):
            return False
        return self._spell_is_controllers(game, spell, controller)

    def _spell_is_controllers(
        self, game: "GameState", spell: Any, controller: Any
    ) -> bool:
        """Return ``True`` if *spell* belongs to Witherbloom's controller.

        The grant only applies to spells *you* cast.  With no fully live cast
        pipeline, a spell is treated as the controller's when it is in the
        controller's hand (the observable proxy the tests use) or already
        controlled by the controller (a spell on the stack).
        """
        spell_controller = getattr(spell, "controller", None)
        if spell_controller is controller:
            return True
        if game.get_hand(controller).contains(spell):
            return True
        for player in game.players:
            if player is controller:
                continue
            if game.get_hand(player).contains(spell):
                return False
        return False

    # ------------------------------------------------------------------
    # Continuous grant + granted-reduction pipeline wiring.
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Install the continuous affinity grant and the granted-reduction hook."""
        self._apply_affinity_grant(game)
        self._register_affinity_reduction(game)

    def register_replacement_effects(self, game: "GameState") -> None:
        """Refresh the affinity grant whenever effects are recomputed."""
        self._apply_affinity_grant(game)
        self._register_affinity_reduction(game)

    def _apply_affinity_grant(self, game: "GameState") -> None:
        """Flag every instant/sorcery in the controller's hand as having affinity.

        Reuses the additive :func:`engine.affinity.grant_affinity_to_hand` so the
        grant is observable both via :meth:`has_affinity_for_creatures` and via
        the ``affinity_for_creatures`` flag written onto each affected hand card.
        No-ops (and clears stale flags) while Witherbloom is off the battlefield.
        """
        from engine.affinity import clear_affinity_flags, grant_affinity_to_hand

        controller = self.controller
        if controller is None:
            return
        if not _is_on_battlefield(game, self):
            clear_affinity_flags(game, self)
            return
        grant_affinity_to_hand(game, self, controller)

    def _register_affinity_reduction(self, game: "GameState") -> None:
        """Drive the granted affinity reduction through the cast/cost pipeline.

        Registers (per source) a granted per-spell reduction so that when the
        controller casts a granted instant/sorcery, ``cast_spell`` /
        ``get_cost_reduction`` lowers its generic cost by the number of creatures
        the controller controls (clamped to the spell's generic) — exactly like
        affinity.  The grant applies only to the controller's instants/sorceries
        while Witherbloom is on the battlefield; otherwise it contributes 0.
        """
        from engine.affinity import (
            clear_affinity_grant,
            is_instant_or_sorcery,
            register_affinity_grant,
        )

        controller = self.controller
        if controller is None:
            return
        if not _is_on_battlefield(game, self):
            clear_affinity_grant(game, self)
            return

        source = self

        def _applies(g: Any, spell: Any, ctrl: Any) -> bool:
            # The grant functions only while Witherbloom is on the battlefield.
            if not _is_on_battlefield(g, source):
                return False
            grant_controller = getattr(source, "controller", None)
            if grant_controller is None:
                return False
            # Only the granting controller's spells receive the reduction.
            if ctrl is not grant_controller:
                return False
            # Only instant/sorcery spells — not creature spells, not the
            # granting permanent's own (creature) spell.
            if spell is source:
                return False
            return is_instant_or_sorcery(spell)

        def _resolver(g: Any, spell: Any, ctrl: Any) -> int:
            # Affinity for creatures: {1} less per creature the controller
            # controls.
            return _count_creatures_controlled(g, ctrl)

        register_affinity_grant(game, source, controller, _resolver, _applies)
