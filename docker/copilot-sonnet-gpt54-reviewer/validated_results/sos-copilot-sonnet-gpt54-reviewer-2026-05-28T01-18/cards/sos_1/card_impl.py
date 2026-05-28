"""Card implementation for The Dawning Archaic (SOS #1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell_free, resolve_top
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — 7/7 — Legendary Creature — Avatar.

    This spell costs {1} less to cast for each instant and sorcery card in your
    graveyard.
    Reach.
    Whenever The Dawning Archaic attacks, you may cast target instant or sorcery
    card from your graveyard without paying its mana cost. If that spell would
    be put into your graveyard, exile it instead.

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
            "This spell costs {1} less to cast for each instant and sorcery card in "
            "your graveyard.\nReach\nWhenever The Dawning Archaic attacks, you may cast "
            "target instant or sorcery card from your graveyard without paying its mana "
            "cost. If that spell would be put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)
        # Holds the spell chosen to cast via the attack trigger (set externally
        # by test code or by the game engine's targeting logic).
        self.chosen_graveyard_spell: Any = None

    # ------------------------------------------------------------------
    # Cost-reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return {1} per instant or sorcery card in the controller's graveyard."""
        controller = self.controller
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
    # Triggered ability: whenever this attacks, cast instant/sorcery from graveyard
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger for casting from the graveyard."""
        source = self

        def _condition(game: Any, event: AttacksTriggeredEvent) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(game: "GameState") -> None:
            # Retrieve the spell to cast (set externally before resolution).
            spell = getattr(source, "chosen_graveyard_spell", None)
            if spell is None:
                return
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Verify the spell is still in the controller's graveyard.
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(spell):
                return

            # Verify the chosen card is an instant or sorcery.
            spell_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in spell_types and CardType.SORCERY not in spell_types:
                return

            # Reset the chosen spell so the trigger is stateless between attacks.
            source.chosen_graveyard_spell = None

            # Mark the spell for exile-on-resolution (instead of graveyard).
            # This flag is read by _resolve_spell in engine/casting.py.
            spell._exile_on_resolve = True  # type: ignore[attr-defined]

            # Cast the spell for free using the full spell-casting pipeline.
            # This moves the card from the graveyard to the stack, fires on_cast,
            # and pushes a StackObject so the spell can be responded to.
            cast_spell_free(game, controller, spell, Zone.GRAVEYARD)

            # Immediately resolve the spell from the stack (simulates priority
            # passing in a unit-test context).
            resolve_top(game)

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
