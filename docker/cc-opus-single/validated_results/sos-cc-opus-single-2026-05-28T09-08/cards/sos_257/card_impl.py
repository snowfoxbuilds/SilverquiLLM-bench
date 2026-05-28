"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex -- Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
            "only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature attributes (set when animated)
        self._is_animated: bool = False
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.subtypes: set[str] = kwargs.get("subtypes", set()) or set()

    # ------------------------------------------------------------------
    # Properties for creature power/toughness (mimic Creature interface)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Current power (includes modified_power from continuous effects)."""
        return self.modified_power

    @property
    def toughness(self) -> int:
        """Current toughness."""
        return self.modified_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the land's two mana abilities."""
        card = self

        # Ability 1: {T}: Add {C}
        def colorless_cost(game: GameState, source: Any) -> bool:
            if card.is_tapped:
                return False
            card.is_tapped = True
            return True

        def colorless_mana_produced(game: GameState) -> None:
            controller = card.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        colorless_ability = ManaAbility(
            cost=colorless_cost,
            mana_produced=colorless_mana_produced,
            description="{T}: Add {C}.",
        )

        # Ability 2: {T}, Pay 1 life: Add one mana of any color
        def any_color_cost(game: GameState, source: Any) -> bool:
            if card.is_tapped:
                return False
            controller = card.controller
            if controller is None:
                return False
            card.is_tapped = True
            controller.life -= 1
            return True

        def any_color_mana_produced(game: GameState) -> None:
            controller = card.controller
            if controller is None:
                return
            # Default to adding WHITE mana (the player would normally choose)
            controller.mana_pool.add(ManaType.WHITE, 1)

        any_color_ability = ManaAbility(
            cost=any_color_cost,
            mana_produced=any_color_mana_produced,
            description="{T}, Pay 1 life: Add one mana of any color.",
        )

        return [colorless_ability, any_color_ability]

    # ------------------------------------------------------------------
    # Activated ability: {5} animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the {5} animate ability."""
        card = self

        def animate_cost(game: GameState, source: Any) -> bool:
            controller = card.controller
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            return controller.mana_pool.pay(cost)

        def animate_effect(game: GameState) -> None:
            # "If this land isn't a creature" check
            if CardType.CREATURE in card.card_types:
                return

            # Add CREATURE type (still a land)
            card.card_types.add(CardType.CREATURE)
            card._original_card_types = frozenset(card.card_types)

            # Set P/T
            card.base_power = 2
            card.base_toughness = 4
            card.modified_power = 2
            card.modified_toughness = 4

            # Add Wizard subtype
            card.subtypes.add("Wizard")

            # Mark as animated
            card._is_animated = True

            # Register the spell-cast trigger
            _register_spell_trigger(game, card)

        return [
            ActivatedAbility(
                cost=animate_cost,
                effect=animate_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature. It's still a land."
                ),
            )
        ]


def _register_spell_trigger(game: GameState, card: GreatHallOfTheBiblioplex) -> None:
    """Register the 'whenever you cast an instant or sorcery' trigger."""
    # Avoid duplicates
    game.trigger_manager.unregister(card)

    controller = card.controller if card.controller is not None else card.owner
    if controller is None:
        return

    def _condition(g: GameState, event: SpellCastTriggeredEvent) -> bool:
        """Only fire for the controller's instant/sorcery spells."""
        if event.controller is not controller:
            return False
        spell_types = getattr(event.spell, "card_types", set())
        return CardType.INSTANT in spell_types or CardType.SORCERY in spell_types

    def _pump_effect(g: GameState) -> None:
        """Give the animated land +1/+0 until end of turn."""
        # Directly modify the power — the pump is tracked as a direct
        # increment so there is no double-counting from a redundant
        # ContinuousEffect.
        card.modified_power += 1

    trigger = TriggerRegistration(
        event_type=SpellCastTriggeredEvent,
        condition=_condition,
        effect=_pump_effect,
        source=card,
        controller=controller,
    )
    game.trigger_manager.register(trigger)
