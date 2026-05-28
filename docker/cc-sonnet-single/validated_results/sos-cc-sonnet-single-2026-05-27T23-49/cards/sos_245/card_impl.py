"""Card implementation for Witherbloom, the Balancer (SOS #245).

Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5

Affinity for creatures (This spell costs {1} less to cast for each creature you control.)
Flying, deathtouch
Instant and sorcery spells you cast have affinity for creatures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import LeavesBattlefieldTriggeredEvent, SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class WitherbloomTheBalancer(Creature):
    """Witherbloom, the Balancer — {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Witherbloom, the Balancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{B}{G}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Affinity for creatures (This spell costs {1} less to cast for each "
            "creature you control.)\n"
            "Flying, deathtouch\n"
            "Instant and sorcery spells you cast have affinity for creatures.",
        )
        # Supertypes: Legendary
        supertypes = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["supertypes"] = supertypes
        # Subtypes: Elder Dragon
        subtypes = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs["subtypes"] = subtypes
        # Keywords: Flying + Deathtouch
        existing_kw = kwargs.get("keywords") or Keyword(0)
        kwargs["keywords"] = existing_kw | Keyword.FLYING | Keyword.DEATHTOUCH

        super().__init__(**kwargs)

        # Reference to the cost reducer entry we register in active_cost_reducers,
        # so we can remove it if needed.
        self._cost_reducer_entry: dict | None = None

    # ------------------------------------------------------------------
    # Affinity for creatures — self cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} less per creature the controller controls.

        Capped at the generic portion of the mana cost (6).
        """
        controller = self.controller
        if controller is None:
            return 0

        battlefield = game.get_battlefield(controller)
        count = 0
        for obj in battlefield.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                count += 1

        # Cap at the generic portion of {6}{B}{G} → 6
        generic = self.mana_cost.generic if self.mana_cost else 0
        return min(count, generic)

    # ------------------------------------------------------------------
    # Triggered abilities — "instants and sorceries you cast have affinity"
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the affinity-grant trigger and cost reducer.

        1. Registers a SpellCastTriggeredEvent trigger whose condition
           fires only when the controller casts an instant or sorcery.
        2. Adds an entry to game.active_cost_reducers so that the
           casting pipeline reduces the cost of instants/sorceries by
           the number of creatures the controller controls.
        """
        source = self

        # --- SpellCastTriggeredEvent trigger (for trigger registration tests) ---

        def _condition(g: "GameState", event: SpellCastTriggeredEvent) -> bool:
            """Fire only for controller's instants and sorceries."""
            # Check caster is the controller
            caster = getattr(event, "player", None)
            ctrl = getattr(source, "controller", None)
            if caster is not ctrl:
                return False
            # Check spell is instant or sorcery
            spell_card = getattr(event, "card", None)
            if spell_card is None:
                spell_obj = getattr(event, "spell", None)
                spell_card = getattr(spell_obj, "source", None) if spell_obj is not None else None
            if spell_card is None:
                return False
            card_types = getattr(spell_card, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _effect(g: "GameState") -> None:
            """No-op effect — cost reduction is handled via active_cost_reducers."""
            # The affinity reduction is applied at cast time via active_cost_reducers.
            # This trigger fires after the spell is on the stack, so no further
            # action is required here.
            pass

        controller = getattr(self, "controller", None) or (
            game.players[0] if game.players else None
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )

        # --- active_cost_reducers entry for casting pipeline ---

        def _reducer_condition(card: Any) -> bool:
            """Applies to instant and sorcery cards."""
            card_types = getattr(card, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _reducer_reduction(g: "GameState", ctrl: Any) -> int:
            """Count creatures the casting player controls."""
            if ctrl is None:
                return 0
            # Only apply if the source (Witherbloom) is on the ctrl's battlefield
            bf = g.get_battlefield(ctrl)
            if not bf.contains(source):
                return 0
            count = 0
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    count += 1
            return count

        reducer_entry: dict = {
            "source": source,
            "condition": _reducer_condition,
            "reduction": _reducer_reduction,
        }
        self._cost_reducer_entry = reducer_entry
        # Remove any existing entry for this source before appending to
        # prevent doubled reductions if register_triggers is called again
        # (e.g. after a blink/flicker).
        game.active_cost_reducers[:] = [
            e for e in game.active_cost_reducers if e.get("source") is not source
        ]
        game.active_cost_reducers.append(reducer_entry)

        # --- LeavesBattlefieldTriggeredEvent: clean up reducer entry on LTB ---

        def _ltb_condition(g: "GameState", event: LeavesBattlefieldTriggeredEvent) -> bool:
            """Fire only when this permanent leaves the battlefield."""
            return event.permanent is source

        def _ltb_effect(g: "GameState") -> None:
            """Remove the active_cost_reducers entry when Witherbloom leaves."""
            g.active_cost_reducers[:] = [
                e for e in g.active_cost_reducers if e.get("source") is not source
            ]

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_ltb_condition,
                effect=_ltb_effect,
                source=source,
                controller=controller,
            )
        )
