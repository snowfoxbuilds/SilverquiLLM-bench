"""Card implementation for Witherbloom, the Balancer (SOS 245).

Witherbloom is a {6}{B}{G} 5/5 Legendary Elder Dragon with:

* **Affinity for creatures** — "This spell costs {1} less to cast for each
  creature you control." (a self cost reduction, modelled via
  :meth:`cost_reduction`).
* **Flying, deathtouch** (evergreen keywords).
* "Instant and sorcery spells you cast have affinity for creatures." (a static
  grant of the same affinity to the controller's instant/sorcery spells while
  Witherbloom is on the battlefield).

Affinity is intentionally NOT a :class:`~engine.types.Keyword` enum member (the
enum is pinned at 16 members by ``engine_tests/test_types.py``); it is surfaced
through the cost-reduction hook plus rules text.

The granted affinity (ability #3) reaches the engine through the additive
``affinity_for_creatures_grant(game, spell, controller)`` grant method, which
``engine.casting.get_cost_reduction`` consults for any spell being cast.  The
grant is scoped (controller-only, instant/sorcery only, only while Witherbloom
is on the battlefield) and is non-sticky / derived dynamically, mirroring the
miracle grant model in ``engine/miracle.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _count_creatures_controlled(game: Any, controller: Any) -> int:
    """Return the number of creatures *controller* controls on the battlefield."""
    if controller is None:
        return 0
    count = 0
    for obj in game.get_battlefield(controller).get_all():
        if CardType.CREATURE in getattr(obj, "card_types", set()):
            count += 1
    return count


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} 5/5 Legendary Elder Dragon.

    Affinity for creatures.  Flying, deathtouch.  Instant and sorcery spells
    you cast have affinity for creatures.

    SOS collector number 245.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.DEATHTOUCH)
        kwargs.setdefault("colors", {Color.BLACK, Color.GREEN})
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for "
            "each creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Own Affinity for creatures (self cost reduction)
    # ------------------------------------------------------------------
    def cost_reduction(self, game: "GameState") -> int:
        """Affinity for creatures: reduce by {1} for each creature you control.

        Counts every creature the controller controls on the battlefield —
        including Witherbloom itself once it is on the battlefield, but
        excluding opponents' creatures and noncreature permanents.  The engine
        clamps the result to the generic portion of the mana cost.
        """
        return _count_creatures_controlled(game, self.controller)

    # ------------------------------------------------------------------
    # Granted affinity — instant/sorcery spells you cast (ability #3)
    # ------------------------------------------------------------------
    def affinity_for_creatures_grant(
        self, game: "GameState", spell: Any, controller: "Player"
    ) -> int:
        """Grant affinity for creatures to *controller*'s instant/sorcery spells.

        Returns the generic reduction (number of creatures *controller*
        controls) to apply to *spell*, or 0 when the grant does not apply.

        The grant is scoped:

        * Witherbloom must be on the battlefield (this method is only consulted
          for permanents on a battlefield, but we guard defensively).
        * Only *Witherbloom's* controller's spells qualify.
        * Only instant and sorcery spells qualify (not creature / other spells).

        ``engine.casting.get_cost_reduction`` clamps the returned value to the
        spell's generic mana cost.
        """
        own_controller = self.controller
        if own_controller is None or controller is None:
            return 0
        if controller is not own_controller:
            return 0
        spell_types = getattr(spell, "card_types", set())
        if not spell_types & {CardType.INSTANT, CardType.SORCERY}:
            return 0
        return _count_creatures_controlled(game, controller)

    def on_resolve(self, game: GameState) -> None:
        # Witherbloom is a creature permanent; its abilities are static, so
        # resolution itself is a no-op (the permanent simply enters play).
        pass
