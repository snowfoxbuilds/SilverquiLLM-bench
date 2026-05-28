"""Card implementation for The Dawning Archaic (SOS 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7.

    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost.  If that
    spell would be put into your graveyard, exile it instead.

    SOS collector number 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{10}"))
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        # Ensure supertypes includes LEGENDARY.
        supertypes: set[Supertype] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["supertypes"] = supertypes
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Return count of instant and sorcery cards in controller's graveyard."""
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
    # Triggers
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the attack trigger for casting from graveyard."""
        from engine.events import AttacksTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: Any) -> bool:
            return event.creature is source or event.attacker is source

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free
            from engine.events import MoveToGraveyardReplacementEvent
            from engine.replacement_effects import ReplacementEffect

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            graveyard = game.get_graveyard(ctrl)
            # Find all instants and sorceries in the graveyard.
            candidates = [
                c for c in graveyard.get_all()
                if CardType.INSTANT in getattr(c, "card_types", set())
                or CardType.SORCERY in getattr(c, "card_types", set())
            ]
            if not candidates:
                return

            # The cast is optional — ask the controller if they want to cast.
            try:
                wants_to_cast = ctrl.choose_yes_no(
                    "You may cast target instant or sorcery from your graveyard "
                    "without paying its mana cost."
                )
            except Exception:
                # Default to yes when no scripted answer is available.
                wants_to_cast = True

            if not wants_to_cast:
                return

            # Choose which spell to cast.
            try:
                chosen = ctrl.choose(
                    candidates,
                    "Choose instant or sorcery to cast from graveyard",
                )
            except Exception:
                chosen = candidates[0]
            if chosen is None:
                return

            # Register a replacement effect so that if the chosen spell would
            # be put into the graveyard after resolving, it goes to exile instead.
            # This satisfies the oracle text: "If that spell would be put into
            # your graveyard, exile it instead."
            chosen_card = chosen  # close over the specific card chosen

            def _exile_replacement(
                g: "GameState", event: MoveToGraveyardReplacementEvent
            ) -> MoveToGraveyardReplacementEvent:
                event.destination = "exile"
                return event

            def _replacement_condition(
                g: "GameState", event: MoveToGraveyardReplacementEvent
            ) -> bool:
                # Fire only for this specific card being moved from the stack.
                return (
                    getattr(event, "card_obj", None) is chosen_card
                    or getattr(event, "card", None) is chosen_card
                )

            replacement = ReplacementEffect(
                event_type=MoveToGraveyardReplacementEvent,
                source=chosen_card,
                condition=_replacement_condition,
                replacement=_exile_replacement,
                controller=ctrl,
            )
            game.replacement_manager.register(replacement)

            # Cast the chosen spell using the free-cast pipeline — it goes on
            # the stack and can be countered, responded to, and resolves normally.
            try:
                cast_spell_free(game, ctrl, chosen, Zone.GRAVEYARD)
            except Exception:
                # If casting fails (e.g. targeting failed), remove the
                # replacement effect we just registered.
                game.replacement_manager.unregister(chosen_card)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
