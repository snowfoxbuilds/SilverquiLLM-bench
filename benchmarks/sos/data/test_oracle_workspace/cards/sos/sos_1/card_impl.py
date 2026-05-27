"""Card implementation for The Dawning Archaic.

Oracle text:
    This spell costs {1} less to cast for each instant and sorcery card in
    your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — Legendary Creature — Avatar.

    {10} colorless, 7/7, Reach.
    Cost reduction: {1} less per instant/sorcery in your graveyard.
    Attack trigger: may cast target instant/sorcery from GY free; if that
    spell would go to GY on resolve/fizzle, exile it instead.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "The Dawning Archaic")
        kwargs.setdefault("mana_cost", ManaCost(generic=10))
        kwargs.setdefault("card_types", set())
        kwargs["card_types"] = kwargs["card_types"] | {CardType.CREATURE}
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = kwargs["supertypes"] | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", {"Avatar"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 7)
        kwargs.setdefault("base_toughness", 7)
        kwargs.setdefault("rules_text",
            "This spell costs {1} less to cast for each instant and sorcery "
            "card in your graveyard.\nReach\nWhenever The Dawning Archaic "
            "attacks, you may cast target instant or sorcery card from your "
            "graveyard without paying its mana cost. If that spell would be "
            "put into your graveyard, exile it instead.")
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Cost reduction
    # ------------------------------------------------------------------

    def cost_reduction(self, game: GameState) -> int:
        """Return count of instant/sorcery cards in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        gy = controller.zones[Zone.GRAVEYARD].get_all()
        count = 0
        for card in gy:
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Attack trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the attack trigger with targeting and may-choice semantics.

        Per MTG rules, the target is locked in when the trigger goes on the
        stack. The TriggerRegistration stores valid targets at trigger-fire
        time via ``_locked_targets``. During resolution, the controller
        makes the may-choice and (if multiple targets) selects which target.
        """
        # Store valid targets when the trigger fires (target lock-in).
        # This list is captured per-fire via closure.
        self._locked_targets: list[Any] = []

        def _condition(g: GameState, event: Any) -> bool:
            if not (
                getattr(event, "creature", None) is self
                or getattr(event, "attacker", None) is self
            ):
                return False
            # Check that at least one valid target exists (if no legal
            # targets, the trigger cannot go on the stack per MTG rules).
            controller = self.controller
            if controller is None:
                return False
            gy = controller.zones[Zone.GRAVEYARD]
            valid = [
                card for card in gy.get_all()
                if CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            ]
            if not valid:
                return False
            # Lock in the valid target pool at trigger-fire time.
            self._locked_targets = valid
            return True

        trigger = TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=lambda g: self._resolve_attack_trigger(g),
            source=self,
            controller=self.controller,
        )
        game.trigger_manager.register(trigger)

    def _resolve_attack_trigger(self, game: GameState) -> None:
        """Resolve the attack trigger: may-choice then cast from locked targets."""
        controller = self.controller
        if controller is None:
            return

        # Use locked targets if available (trigger system path), otherwise
        # find current valid targets (direct-call path for legacy compat).
        targets = getattr(self, "_locked_targets", None)
        if not targets:
            gy = controller.zones[Zone.GRAVEYARD]
            targets = [
                card for card in gy.get_all()
                if CardType.INSTANT in getattr(card, "card_types", set())
                or CardType.SORCERY in getattr(card, "card_types", set())
            ]

        if not targets:
            return

        # May choice — decline means no cast.
        may_cast = controller.choose_yes_no(
            "Cast an instant or sorcery from your graveyard without paying its mana cost?"
        )
        if not may_cast:
            return

        # Choose target card from the locked pool.
        if len(targets) == 1:
            target_card = targets[0]
        else:
            target_card = controller.choose_card(
                targets, "Choose instant or sorcery to cast from graveyard"
            )
        if target_card is None:
            return

        # Register a one-shot replacement effect: if this spell would go
        # to graveyard, exile it instead.
        _register_exile_replacement(game, target_card, controller)

        # Cast the spell free from graveyard.
        from engine.casting import cast_spell_free
        cast_spell_free(game, controller, target_card, Zone.GRAVEYARD)

        # Clear locked targets after use.
        self._locked_targets = []


def _register_exile_replacement(
    game: Any,
    target_card: Any,
    controller: Any,
) -> None:
    """Register a one-shot replacement effect scoped to target_card.

    If target_card would be put into a graveyard (on resolve or fizzle),
    exile it instead.
    """

    # Use a mutable container to track one-shot usage
    used = [False]

    def _condition(g: Any, event: Any) -> bool:
        if used[0]:
            return False
        # Check if the card moving to GY is our target
        card = getattr(event, "card", None)
        if card is None:
            # Try other attribute names
            card = getattr(event, "creature", None) or getattr(event, "permanent", None)
        return card is target_card

    def _replacement(g: Any, event: Any) -> Any:
        used[0] = True
        # Redirect destination to exile
        event.destination = "exile"
        # Unregister this one-shot effect
        g.replacement_manager.unregister(target_card)
        return event

    effect = ReplacementEffect(
        event_type=MoveToGraveyardReplacementEvent,
        source=target_card,
        condition=_condition,
        replacement=_replacement,
        controller=controller,
    )
    game.replacement_manager.register(effect)

