"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    Reach.
    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
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
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} per instant/sorcery card in the controller's graveyard.

        The engine clamps this value to the generic portion of the mana cost
        (see :func:`engine.casting.get_cost_reduction`), so colored mana is
        never reduced and the value never drives generic below zero.
        """
        controller = getattr(self, "controller", None)
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Attack trigger: free-cast an instant/sorcery from your graveyard
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger for the optional free cast."""
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.creature is source

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # "you may" — ask before doing anything else.
            if not controller.choose_yes_no(
                "Cast an instant or sorcery from your graveyard without "
                "paying its mana cost?"
            ):
                return

            # Gather legal targets: instant/sorcery cards in your graveyard.
            graveyard = game.get_graveyard(controller)
            legal = [
                card
                for card in graveyard.get_all()
                if (
                    CardType.INSTANT in getattr(card, "card_types", set())
                    or CardType.SORCERY in getattr(card, "card_types", set())
                )
            ]
            if not legal:
                # Said yes but there is nothing to cast — safe no-op.
                return

            chosen = controller.choose_card(
                legal, "Choose an instant or sorcery to cast from your graveyard"
            )
            if chosen is None or chosen not in legal:
                return

            # "If that spell would be put into your graveyard, exile it
            # instead." Flag the spell so the resolution pipeline redirects
            # its stack -> graveyard move to exile.
            chosen._exile_instead_of_graveyard = True  # type: ignore[attr-defined]
            cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
