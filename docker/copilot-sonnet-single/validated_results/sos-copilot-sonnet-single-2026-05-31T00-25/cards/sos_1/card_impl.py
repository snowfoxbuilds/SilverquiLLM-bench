"""Card implementation for The Dawning Archaic (sos_1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return True if *card* is an instant or sorcery."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7

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
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.",
        )
        super().__init__(**kwargs)
        # Tracks the spell currently being cast via the attack trigger so that
        # the replacement effect knows which spell to redirect to exile.
        self._graveyard_cast_spell: Any | None = None

    # ------------------------------------------------------------------
    # Cost reduction — {1} less for each instant/sorcery in graveyard
    # ------------------------------------------------------------------

    def cost_reduction(self, game: "GameState") -> int:
        """Reduce cast cost by 1 for each instant/sorcery in your graveyard.

        Capped at the card's generic mana cost (10) so the cost never goes
        below 0.
        """
        controller = self.controller
        if controller is None:
            return 0
        graveyard = game.get_graveyard(controller)
        count = sum(
            1 for card in graveyard.get_all() if _is_instant_or_sorcery(card)
        )
        # Cap at the generic mana cost so reduction never exceeds the CMC.
        return min(count, self.mana_cost.generic)

    # ------------------------------------------------------------------
    # Attack trigger — cast instant/sorcery from graveyard for free
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import AttacksTriggeredEvent
        from engine.player import ScriptExhaustedError
        from engine.triggers import TriggerRegistration

        source = self

        def _attack_condition(game: "GameState", event: Any) -> bool:
            return (
                getattr(event, "creature", None) is source
                or getattr(event, "attacker", None) is source
            )

        def _attack_effect(game: "GameState") -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            graveyard = game.get_graveyard(controller)
            targets = [
                card for card in graveyard.get_all()
                if _is_instant_or_sorcery(card)
            ]
            if not targets:
                return

            # Ask the player which instant/sorcery to cast (optional).
            # Fall back to the first option in test environments without a script.
            try:
                chosen = controller.choose(
                    targets, "Choose an instant or sorcery to cast from graveyard"
                )
            except ScriptExhaustedError:
                chosen = targets[0]

            if chosen is None:
                return

            # Re-validate: card must still be in graveyard.
            if not graveyard.contains(chosen):
                return

            # Mark the spell so the replacement effect can exile it.
            source._graveyard_cast_spell = chosen

            # Ensure the exile-replacement effect is registered now (it must be
            # active before the instant/sorcery resolves and tries to move to
            # graveyard, which may happen in the same trigger-resolution chain).
            source.register_replacement_effects(game)

            # Cast the spell for free from graveyard.
            from engine.casting import cast_spell_free
            try:
                cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)
            except Exception:
                # Casting failed — clear the marker.
                source._graveyard_cast_spell = None

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_attack_condition,
            effect=_attack_effect,
            source=self,
            controller=controller,
        ))

    # ------------------------------------------------------------------
    # Replacement effect — exile the spell instead of going to graveyard
    # ------------------------------------------------------------------

    def register_replacement_effects(self, game: "GameState") -> None:
        from engine.events import SpellMovesToGraveyardReplacementEvent
        from engine.replacement_effects import ReplacementEffect

        # Guard against double-registration (may be called from trigger effect
        # and also separately via register_replacement_effects).
        if any(e.source is self for e in game.replacement_manager.get_effects()):
            return

        archaic = self

        def _condition(game: "GameState", event: Any) -> bool:
            """Fire only for the spell currently being cast via our trigger."""
            return (
                archaic._graveyard_cast_spell is not None
                and getattr(event, "spell", None) is archaic._graveyard_cast_spell
            )

        def _replacement(game: "GameState", event: Any) -> Any:
            """Redirect destination from graveyard to exile."""
            event.destination = "exile"
            archaic._graveyard_cast_spell = None
            return event

        game.replacement_manager.register(ReplacementEffect(
            event_type=SpellMovesToGraveyardReplacementEvent,
            source=self,
            condition=_condition,
            replacement=_replacement,
            controller=getattr(self, "controller", None),
        ))
