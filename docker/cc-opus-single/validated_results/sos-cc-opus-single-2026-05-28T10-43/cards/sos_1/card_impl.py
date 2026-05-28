"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.events import AttacksTriggeredEvent

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic -- {10} -- 7/7 -- Legendary Creature - Avatar.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
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
            "card in your graveyard.\n"
            "Reach\n"
            "Whenever The Dawning Archaic attacks, you may cast target instant "
            "or sorcery card from your graveyard without paying its mana cost. "
            "If that spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: GameState) -> int:
        """Return the number of instant and sorcery cards in owner's graveyard.

        This spell costs {1} less to cast for each instant and sorcery card
        in your graveyard. Returns the raw count; the engine clamps generic
        mana to >= 0 in get_cost_reduction().
        """
        # Use controller (the caster) to determine "your graveyard".
        # Fall back to owner if controller is not set.
        player = self.controller or self.owner
        if player is None:
            return 0
        graveyard = game.get_graveyard(player)
        count = 0
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Attack trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the attack trigger for casting from graveyard."""
        from engine.triggers import TriggerRegistration
        from engine.casting import cast_spell_free

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            """Only fire when The Dawning Archaic itself attacks."""
            return event.creature is source

        def _effect(game: GameState) -> None:
            """You may cast target instant or sorcery from your graveyard
            without paying its mana cost. If that spell would be put into
            your graveyard, exile it instead."""
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Find valid targets: instant or sorcery cards in controller's graveyard
            graveyard = game.get_graveyard(ctrl)
            valid_targets = []
            for card in graveyard.get_all():
                card_types = getattr(card, "card_types", set())
                if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                    valid_targets.append(card)

            if not valid_targets:
                return

            # Let the player choose a target
            try:
                chosen = ctrl.choose(valid_targets, "Choose target instant or sorcery card from your graveyard")
            except Exception:
                return

            if chosen is None:
                return

            # Verify the chosen card is actually a valid target
            chosen_types = getattr(chosen, "card_types", set())
            if CardType.INSTANT not in chosen_types and CardType.SORCERY not in chosen_types:
                return

            # "You may cast" -- ask if the player wants to cast it
            try:
                wants_to_cast = ctrl.choose_yes_no(
                    f"Cast {getattr(chosen, 'name', 'card')} without paying its mana cost?"
                )
            except Exception:
                return

            if not wants_to_cast:
                return

            # Mark the card for exile replacement: if it would go to
            # graveyard after resolution, exile it instead.
            chosen._dawning_archaic_exile = True  # type: ignore[attr-defined]

            # Cast the spell from the graveyard without paying mana cost
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                # Clean up the marker if casting fails
                if hasattr(chosen, "_dawning_archaic_exile"):
                    del chosen._dawning_archaic_exile
                return

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
