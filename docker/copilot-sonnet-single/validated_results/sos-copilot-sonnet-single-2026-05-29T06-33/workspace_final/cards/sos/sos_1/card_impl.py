"""Card implementation for The Dawning Archaic.

# UNVERIFIED: player may decline the cast trigger — DeterministicPlayer lacks clear 'decline may-trigger' script path
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.casting import cast_spell_free
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class TheDawningArchaic(Creature):
    """The Dawning Archaic — {10} — Legendary Creature — Avatar (7/7).

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
            "This spell costs {1} less to cast for each instant and sorcery card "
            "in your graveyard.\nReach\nWhenever The Dawning Archaic attacks, you "
            "may cast target instant or sorcery card from your graveyard without "
            "paying its mana cost. If that spell would be put into your graveyard, "
            "exile it instead.",
        )
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """Return 1 less for each instant or sorcery in controller's graveyard."""
        controller = self.controller
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD].get_all()
        return sum(
            1
            for card in graveyard
            if CardType.INSTANT in getattr(card, "card_types", set())
            or CardType.SORCERY in getattr(card, "card_types", set())
        )

    def register_triggers(self, game: "GameState") -> None:
        """Register the 'whenever attacks' trigger."""
        archaic = self
        controller = self.controller

        def condition(g: "GameState", event: Any) -> bool:
            return event.attacker is archaic

        def effect(g: "GameState") -> None:
            _resolve_attack_trigger(g, archaic)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=AttacksTriggeredEvent,
                condition=condition,
                effect=effect,
                source=archaic,
                controller=controller,
            )
        )


def _resolve_attack_trigger(game: "GameState", archaic: "TheDawningArchaic") -> None:
    """Resolve the attack trigger: cast an instant or sorcery from graveyard for free.

    Finds valid instant/sorcery cards in the controller's graveyard, prompts
    the controller to choose one, then casts it for free via cast_spell_free
    (which properly calls on_cast and on_resolve). After on_resolve executes,
    the card is exiled instead of going to the graveyard, per the card text:
    "If that spell would be put into your graveyard, exile it instead."
    """
    controller = archaic.controller
    if controller is None:
        return

    graveyard_zone = controller.zones[Zone.GRAVEYARD]
    valid_targets = [
        card
        for card in graveyard_zone.get_all()
        if CardType.INSTANT in getattr(card, "card_types", set())
        or CardType.SORCERY in getattr(card, "card_types", set())
    ]

    if not valid_targets:
        return

    # Controller chooses which instant or sorcery to cast for free.
    chosen = controller.choose_card(valid_targets, "Choose an instant or sorcery to cast for free from graveyard")
    if chosen is None or not graveyard_zone.contains(chosen):
        return

    # Cast the spell via the proper free-cast pipeline:
    # - moves card from graveyard to stack zone
    # - calls on_cast hook
    # - pushes a StackObject onto game.stack
    cast_spell_free(game, controller, chosen, Zone.GRAVEYARD)

    # Immediately pop the spell from the stack and resolve it here.
    # (The free-cast triggered by an attack trigger resolves in the same
    # step — the spell does not wait for opponent priority in this simulation.)
    spell_obj = game.stack.pop()

    # Execute the spell's on_resolve effects (deal damage, draw cards, etc.)
    targets = getattr(spell_obj, "targets", None) or []
    if targets:
        chosen.chosen_targets = targets  # type: ignore[attr-defined]
    chosen.on_resolve(game)

    # Remove from stack zone (cast_spell_free placed it there).
    stack_zone = controller.zones[Zone.STACK]
    if stack_zone.contains(chosen):
        stack_zone.remove(chosen)

    # "If that spell would be put into your graveyard, exile it instead."
    exile_zone = controller.zones[Zone.EXILE]
    exile_zone.add(chosen)
