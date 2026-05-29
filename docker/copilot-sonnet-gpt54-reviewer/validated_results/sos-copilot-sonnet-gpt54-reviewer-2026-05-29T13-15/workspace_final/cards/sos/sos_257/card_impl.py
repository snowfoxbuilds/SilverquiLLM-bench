"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from engine.card import Land, ActivatedAbility, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color.  Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", None)
        super().__init__(**kwargs)
        # Power/toughness for creature form (set when {5} activates)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0

    def _reset_characteristics(self) -> None:
        """Reset per-turn power boosts; preserve permanent creature transformation."""
        super()._reset_characteristics()
        # Reset power/toughness to base (clears +1/+0 until EOT bonuses)
        if CardType.CREATURE in self.card_types:
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        # {T}: Add {C}
        def _tap_cost_colorless(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        # {T}, Pay 1 life: Add one mana of any color (restricted to instants/sorceries)
        def _tap_life_cost(game: Any, src: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if ctrl.life <= 0:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_color(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Ask player which color to add (script-driven)
            try:
                chosen_color = ctrl._script.popleft()
            except Exception:
                chosen_color = ManaType.WHITE
            if isinstance(chosen_color, ManaType) and chosen_color != ManaType.COLORLESS:
                ctrl.mana_pool.add(chosen_color, 1)
            else:
                ctrl.mana_pool.add(ManaType.WHITE, 1)

        return [
            ManaAbility(
                cost=_tap_cost_colorless,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_life_cost,
                mana_produced=_add_any_color,
                description="{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    def get_activated_abilities(self, game: "GameState") -> list[ActivatedAbility]:
        source = self

        def _creature_cost(game: Any, src: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            # Already a creature — can't activate again
            if CardType.CREATURE in source.card_types:
                return False
            # Check if player can pay {5}
            cost = ManaCost.parse("{5}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            ctrl.mana_pool.pay(cost)
            return True

        def _creature_effect(game: Any) -> None:
            # Transform the land into a 2/4 Wizard creature
            source.card_types.add(CardType.CREATURE)
            # Make CREATURE permanent (update _original so _reset_characteristics preserves it)
            source._original_card_types = frozenset(source.card_types)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4

        ability = ActivatedAbility(
            cost=_creature_cost,
            effect=_creature_effect,
            description="{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with 'Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.' It's still a land.",
        )
        return [ability]

    def register_triggers(self, game: "GameState") -> None:
        """Register the spell-cast +1/+0 trigger (only active in creature form)."""
        from engine.card import Instant, Sorcery
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            if not isinstance(event.card, (Instant, Sorcery)):
                return False
            # Only fires when Great Hall is in creature form
            return CardType.CREATURE in source.card_types

        def _effect(game: Any) -> None:
            if CardType.CREATURE not in source.card_types:
                return
            # +1/+0 until EOT: directly increment modified_power;
            # _reset_characteristics() resets it to base_power at cleanup.
            source.modified_power += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=getattr(self, "controller", None),
            )
        )
