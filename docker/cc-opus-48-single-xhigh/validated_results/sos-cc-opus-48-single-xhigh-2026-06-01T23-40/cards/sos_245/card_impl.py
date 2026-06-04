"""Card implementation for Witherbloom, the Balancer (SOS 245).

Witherbloom, the Balancer is a ``{6}{B}{G}`` Legendary Creature — Elder
Dragon, 5/5, with flying and deathtouch. It has two affinity-for-creatures
abilities:

    "Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)"
    "Flying, deathtouch"
    "Instant and sorcery spells you cast have affinity for creatures."

Affinity is modeled through the ``cost_reduction(game)`` hook (FDN 6 Claws
Out convention): the engine clamps the returned reduction to the generic
portion of the mana cost in :func:`engine.casting.get_cost_reduction`, so
colored mana is never reduced and generic never drops below zero. No manual
clamp is needed here.

The third ability grants affinity-for-creatures to *other* spells — every
instant and sorcery the controller casts. The default
``get_cost_reduction`` consults only a spell's own ``cost_reduction`` hook,
so — mirroring the SOS 226 casualty-granting and SOS 201 miracle-granting
conventions — the grant is exposed through a getattr-safe capability the
engine's cost-reduction path queries on permanents the caster controls:

* ``grants_affinity_to(spell) -> bool`` — True for instant/sorcery spells.
* ``affinity_reduction(game) -> int`` — the creature count the controller
  controls (the granted reduction value; also the dragon's own affinity
  metric, to which ``cost_reduction`` delegates).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — 5/5 — Legendary Elder Dragon.

    Affinity for creatures.
    Flying, deathtouch.
    Instant and sorcery spells you cast have affinity for creatures.

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
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)
        # Explicit color identity (KEY_DECISIONS sos_13 convention).
        self.colors: list[str] = ["B", "G"]

    # ------------------------------------------------------------------
    # Affinity for creatures — the dragon's OWN cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: reduce cost by 1 per creature you control.

        Delegates to :meth:`affinity_reduction` — the same creature-count
        metric the dragon grants to instants/sorceries — so both abilities
        share one source of truth. The engine clamps the result to the
        generic portion of the cost in
        :func:`engine.casting.get_cost_reduction`, so no manual clamp is
        applied here (FDN 6 convention).
        """
        return self.affinity_reduction(game)

    # ------------------------------------------------------------------
    # Granted affinity (capability) — "Instant and sorcery spells you cast
    # have affinity for creatures."
    # ------------------------------------------------------------------

    def grants_affinity_to(self, spell: Any) -> bool:
        """Return ``True`` if this dragon grants affinity to *spell*.

        Witherbloom grants affinity-for-creatures to every instant and
        sorcery spell; any other card type (creature, land, etc.) gets
        nothing. This is the getattr-safe capability the additive
        cost-reduction hook in :mod:`engine.casting` queries on permanents
        the casting player controls.
        """
        card_types = getattr(spell, "card_types", set())
        return CardType.INSTANT in card_types or CardType.SORCERY in card_types

    def affinity_reduction(self, game: "GameState") -> int:
        """Return the affinity-for-creatures reduction value.

        Equal to the number of creatures the dragon's controller controls —
        the same metric the dragon applies to itself (``cost_reduction``) and
        grants to the controller's instants/sorceries. Returns 0 when there
        is no controller.
        """
        controller = getattr(self, "controller", None)
        if controller is None:
            return 0
        battlefield = game.get_battlefield(controller)
        count = 0
        for obj in battlefield.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                count += 1
        return count
