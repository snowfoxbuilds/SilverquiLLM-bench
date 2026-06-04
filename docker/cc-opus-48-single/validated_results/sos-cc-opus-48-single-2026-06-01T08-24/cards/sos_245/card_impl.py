"""Card implementation for Witherbloom, the Balancer (SOS 245)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    """Return ``True`` if *obj* is a creature permanent."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return ``True`` if *card* is an instant or sorcery card."""
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


def _count_creatures(game: Any, player: Any) -> int:
    """Return the number of creatures *player* controls on the battlefield."""
    if player is None:
        return 0
    try:
        battlefield = game.get_battlefield(player)
    except (AttributeError, KeyError, LookupError):
        return 0
    return sum(1 for obj in battlefield.get_all() if _is_creature(obj))


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in getattr(game, "players", []) or []:
        try:
            if game.get_battlefield(player).contains(obj):
                return True
        except (AttributeError, KeyError, LookupError):
            continue
    return False


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Creature — Elder Dragon.

    - Affinity for creatures (this spell costs {1} less to cast for each creature
      you control). Only the generic portion of the cost is reduced.
    - Flying, deathtouch.
    - Instant and sorcery spells you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\nFlying, deathtouch\nInstant and sorcery "
            "spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Affinity for creatures — reduces this spell's own cost
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce generic mana by 1 for each creature you control.

        Counts creatures the controller controls on the battlefield. While this
        card is being cast it is on the stack (not the battlefield), so it never
        counts itself — matching "for each creature you control".
        """
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        return _count_creatures(game, controller)

    # ------------------------------------------------------------------
    # No targets — Witherbloom's abilities are static; casting it as a
    # creature must not demand a target.
    # ------------------------------------------------------------------

    def get_targets(self, game: "GameState") -> list[Any]:
        """Witherbloom is a vanilla-cast permanent; it advertises no targets."""
        return []

    # ------------------------------------------------------------------
    # Granted affinity — "Instant and sorcery spells you cast have affinity
    # for creatures." Registered as a game-level spell cost reducer that the
    # casting pipeline (engine.casting.get_cost_reduction) sums alongside each
    # spell's own cost_reduction() hook.
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the granted-affinity cost reducer while on the battlefield.

        Idempotent: any reducer previously registered by this same source is
        removed first, so blink/recursion (which re-enters the battlefield and
        re-runs ``register_triggers``) never leaves two identical reducers that
        would double-count the affinity reduction. ``unregister_spell_cost_reducer``
        is a safe no-op when no prior reducer exists.
        """
        source = self

        # Remove any stale/prior reducer with this source before re-registering
        # so only one reducer per source ever exists (prevents double-counting
        # on re-entry and the stale-leak after leaving the battlefield).
        unregister = getattr(game, "unregister_spell_cost_reducer", None)
        if unregister is not None:
            unregister(source)

        def _predicate(g: Any, card: Any, controller: Any) -> bool:
            # Applies only to the controller's OTHER instant/sorcery spells,
            # and only while Witherbloom is on the battlefield.
            if card is source:
                return False
            if not _is_instant_or_sorcery(card):
                return False
            owner_controller = getattr(source, "controller", None) or getattr(
                source, "owner", None
            )
            if owner_controller is None or controller is not owner_controller:
                return False
            return _is_on_battlefield(g, source)

        def _amount(g: Any, card: Any, controller: Any) -> int:
            # Affinity for creatures: {1} less per creature the controller
            # controls. Clamping to the spell's generic is handled centrally.
            return _count_creatures(g, controller)

        register = getattr(game, "register_spell_cost_reducer", None)
        if register is not None:
            register(_predicate, _amount, source=source)
