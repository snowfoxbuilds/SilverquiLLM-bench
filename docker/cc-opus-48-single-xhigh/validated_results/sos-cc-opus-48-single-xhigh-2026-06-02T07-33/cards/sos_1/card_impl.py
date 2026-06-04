"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost reduction — {1} less for each instant/sorcery in your graveyard.
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce the generic cost by {1} per instant/sorcery in your graveyard.

        Only the controller's graveyard is consulted, and only instant and
        sorcery cards count.  The engine clamps the final value so generic
        mana never goes below 0 (see ``engine.casting.get_cost_reduction``).
        """
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Attack trigger — may recast an instant/sorcery from your graveyard.
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger that recasts a graveyard spell for free."""
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            graveyard = ctrl.zones[Zone.GRAVEYARD]
            candidates = [
                c
                for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not candidates:
                return

            # Optional "you may" — ask before committing to a target.
            try:
                wants_to_cast = ctrl.choose_yes_no(
                    "Cast an instant or sorcery from your graveyard "
                    "without paying its mana cost?"
                )
            except Exception:
                wants_to_cast = False
            if not wants_to_cast:
                return

            # Choose the target instant/sorcery card from the graveyard.
            try:
                chosen = ctrl.choose_card(
                    candidates,
                    "instant or sorcery card to cast from your graveyard",
                )
            except Exception:
                chosen = None
            if chosen is None or not graveyard.contains(chosen):
                return

            # "If that spell would be put into your graveyard, exile it
            # instead." — register a stack→graveyard redirect for this spell
            # so that when it finishes resolving it heads to exile.
            from engine.casting import (
                cast_spell_free,
                register_stack_to_graveyard_redirect,
            )

            register_stack_to_graveyard_redirect(game, chosen, "exile")
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                # If the cast fails (e.g. illegal target), clear the redirect
                # so a future natural trip to the graveyard is unaffected.
                from engine.casting import clear_stack_to_graveyard_redirect

                clear_stack_to_graveyard_redirect(game, chosen)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
