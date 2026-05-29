"""Card implementation for sos_245 — Witherbloom, the Balancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AffinityGrantReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5.

    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.
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
            "creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost reduction — Affinity for creatures (self)
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return 1 per creature the controller controls, capped at 6."""
        controller = self.controller
        if controller is None:
            return 0
        battlefield = game.get_battlefield(controller)
        count = sum(
            1
            for obj in battlefield.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )
        # Cap at the generic portion of {6}{B}{G} = 6.
        return min(count, 6)

    # ------------------------------------------------------------------
    # Continuous effect — grant affinity for creatures to instants/sorceries
    # ------------------------------------------------------------------

    def register_replacement_effects(self, game: "GameState") -> None:
        """Grant instants/sorceries the controller casts affinity for creatures.

        Registers a sentinel :class:`~engine.events.AffinityGrantReplacementEvent`
        in the replacement manager (so callers can detect the effect is active)
        and adds a callable to ``game.global_cost_reducers`` that reduces the
        generic cost of instant/sorcery spells by 1 per creature controlled.
        """
        source = self

        # --- Sentinel registration in replacement_manager ---
        # This never actually fires; it is purely a record that Witherbloom
        # has registered an affinity-grant effect while on the battlefield.
        game.replacement_manager.register(
            ReplacementEffect(
                event_type=AffinityGrantReplacementEvent,
                source=source,
                condition=lambda g, ev: False,  # never fires
                replacement=lambda g, ev: ev,
                controller=self.controller,
            )
        )

        # --- Global cost reducer for instants/sorceries ---
        def _affinity_reducer(g: "GameState", card: Any, ctrl: Any) -> int:
            """Reduce instant/sorcery cost by 1 per creature the controller has.

            Witherbloom itself is excluded from the creature count — it grants
            the discount based on *other* creatures the controller controls.

            The reducer self-deactivates when Witherbloom is no longer on the
            battlefield (leaves-the-battlefield cleanup via a membership check).
            """
            # Only applies when this Witherbloom is still the active source.
            # The reducer is tied to this specific Witherbloom instance.
            if source.controller is not ctrl:
                return 0
            # Cleanup guard: if Witherbloom is no longer on the battlefield,
            # the continuous effect lapses and this reducer produces nothing.
            battlefield = g.get_battlefield(ctrl)
            battlefield_objects = list(battlefield.get_all())
            if source not in battlefield_objects:
                return 0
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return 0
            return sum(
                1
                for obj in battlefield_objects
                if obj is not source
                and CardType.CREATURE in getattr(obj, "card_types", set())
            )

        game.global_cost_reducers.append(_affinity_reducer)
