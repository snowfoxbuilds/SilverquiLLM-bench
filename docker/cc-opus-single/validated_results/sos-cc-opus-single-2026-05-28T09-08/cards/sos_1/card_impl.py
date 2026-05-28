"""Card implementation for The Dawning Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return True if *card* is an instant or sorcery."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class TheDawningArchaic(Creature):
    """The Dawning Archaic -- {10} -- Legendary Creature -- Avatar -- 7/7.

    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.

    Reach

    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If
    that spell would be put into your graveyard, exile it instead.

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

    def cost_reduction(self, game: GameState) -> int:
        """Return the number of instants and sorceries in controller's graveyard."""
        controller = self.controller
        if controller is None:
            controller = self.owner
        if controller is None:
            return 0

        graveyard = game.get_graveyard(controller)
        count = 0
        for card in graveyard.get_all():
            if _is_instant_or_sorcery(card):
                count += 1
        return count

    # ------------------------------------------------------------------
    # Targeting (for the attack trigger)
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        """Return target requirements for the attack trigger.

        When The Dawning Archaic is being cast (i.e. it is on the stack),
        it should NOT require any targets — it is a creature spell.  The
        targeting below is only for the attack-trigger ability.  We detect
        the casting context by checking whether *self* is currently in
        the controller's stack zone (the casting pipeline moves the card
        there before calling ``get_targets``).
        """
        # Guard: if the card is on the stack (being cast), return no targets.
        controller = self.controller if self.controller is not None else self.owner
        if controller is not None and hasattr(controller, "zones"):
            try:
                stack_zone = controller.zones[Zone.STACK]
                if stack_zone.contains(self):
                    return []
            except (KeyError, AttributeError):
                pass

        return [
            TargetRequirement(
                filter_fn=_is_instant_or_sorcery,
                description="target instant or sorcery card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
        ]

    # ------------------------------------------------------------------
    # Attack trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the attack trigger for this creature."""
        source = self

        def _condition(game: GameState, event: AttacksTriggeredEvent) -> bool:
            """Only trigger when this creature attacks."""
            return event.creature is source or event.attacker is source

        def _effect(game: GameState) -> None:
            """Cast target instant or sorcery from graveyard for free.

            The target is read from source.chosen_targets (set by the
            test or by the engine's targeting pipeline).
            """
            chosen = getattr(source, "chosen_targets", None)
            if not chosen:
                return

            target_card = chosen[0] if isinstance(chosen, list) else chosen
            if target_card is None:
                return

            # Verify the target is still an instant or sorcery
            if not _is_instant_or_sorcery(target_card):
                return

            controller = source.controller
            if controller is None:
                controller = source.owner
            if controller is None:
                return

            # Verify the target is still in the graveyard
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target_card):
                return

            # Mark this card so the exile-instead-of-graveyard replacement
            # applies only to it.
            target_card._dawning_archaic_free_cast = True  # type: ignore[attr-defined]

            # Cast the spell for free from graveyard.
            # We remove it from the graveyard and put it on the stack,
            # then push a StackObject to resolve it.
            from engine.stack import StackObject

            graveyard.remove(target_card)

            # Set controller/owner for the cast spell
            target_card.controller = controller
            if target_card.owner is None:
                target_card.owner = controller

            # Put on the stack zone
            stack_zone = controller.zones[Zone.STACK]
            stack_zone.add(target_card)

            # Build a StackObject for the free-cast spell
            def _spell_resolve(g: GameState) -> None:
                """Resolve the free-cast spell, then exile it instead of graveyard."""
                # Call the spell's own on_resolve
                target_card.on_resolve(g)

                # Move from stack to exile (instead of graveyard)
                if stack_zone.contains(target_card):
                    stack_zone.remove(target_card)

                owner = target_card.owner if target_card.owner is not None else controller
                exile_zone = g.get_exile(owner)
                exile_zone.add(target_card)

                # Clean up the marker
                if hasattr(target_card, "_dawning_archaic_free_cast"):
                    del target_card._dawning_archaic_free_cast

            spell_stack_obj = StackObject(
                source=target_card,
                controller=controller,
                targets=[],
                on_resolve=_spell_resolve,
            )
            game.stack.push(spell_stack_obj)

        controller = self.controller if self.controller is not None else self.owner
        if controller is None:
            return

        trigger = TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)
