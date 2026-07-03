"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """{T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast "
            "an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 '
            'until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Animation state
        self._animated: bool = False
        self._power_bonus: int = 0  # accumulated +1/+0 bonuses until EOT

    # ------------------------------------------------------------------
    # Mana abilities (index 0 and 1)
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_cost(game: "GameState") -> bool:
            if source.is_tapped:
                return False
            source.is_tapped = True
            return True

        def _colorless_mana(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _colored_cost(game: "GameState") -> bool:
            ctrl = source.controller
            if ctrl is None:
                return False
            if source.is_tapped:
                return False
            if ctrl.life <= 1:  # can't pay 1 life if at 1 or below
                return False
            source.is_tapped = True
            ctrl.life -= 1
            return True

        def _colored_mana(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            # Player chooses a color.
            colors = [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN]
            try:
                chosen_color = ctrl.choose(colors, "Choose a color for restricted mana")
            except Exception:
                chosen_color = ManaType.COLORLESS
            if chosen_color not in colors:
                chosen_color = colors[0]
            # Add as restricted mana (instant/sorcery only).
            ctrl.mana_pool.add_restricted(chosen_color, 1)

        return [
            ManaAbility(
                cost=_colorless_cost,
                mana_produced=_colorless_mana,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_colored_cost,
                mana_produced=_colored_mana,
                description="{T}, Pay 1 life: Add one mana of any color (instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated abilities (index 0: animate)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: "GameState") -> bool:
            # Can only animate if not already a creature.
            if CardType.CREATURE in source.card_types:
                return False
            ctrl = source.controller
            if ctrl is None:
                return False
            # Pay {5} generic mana.
            from engine.types import ManaCost
            cost = ManaCost.parse("{5}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            ctrl.mana_pool.pay(cost)
            return True

        def _animate_effect(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # Already a creature — animation only triggers once
            _do_animate(game, source)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: If not a creature, becomes 2/4 Wizard with pump trigger.",
            ),
        ]

    def register_triggers(self, game: "GameState") -> None:
        """Register pump trigger if animated, and EOT reset trigger."""
        # The pump trigger is registered when animated — see _do_animate.
        pass


def _do_animate(game: "GameState", source: GreatHallOfTheBiblioplex) -> None:
    """Mutate the land into a 2/4 Wizard creature (still a land)."""
    from engine.continuous_effects import DURATION_PERMANENT, ContinuousEffect, Layer, SubLayer
    from engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
    from engine.triggers import TriggerRegistration
    from engine.types import ManaCost

    source._animated = True
    source.card_types = source.card_types | {CardType.CREATURE}
    source.subtypes = getattr(source, "subtypes", set()) | {"Wizard"}
    source.base_power = 2
    source.base_toughness = 4
    source.modified_power = 2
    source.modified_toughness = 4
    # Creatures from animation aren't summoning sick if the land was already on battlefield.
    source.summoning_sick = False
    source.damage_marked = 0
    source.plus_one_counters = 0
    source.minus_one_counters = 0
    source._base_plus_one_counters = 0
    source._base_minus_one_counters = 0
    source.is_attacking = False
    source.is_blocking = False
    source.dealt_deathtouch_damage = False

    ctrl = source.controller

    # Register the spell-cast pump trigger.
    def _pump_condition(g: Any, event: Any) -> bool:
        caster = getattr(event, "controller", None) or getattr(event, "player", None)
        if caster is not source.controller:
            return False
        spell = getattr(event, "spell", None)
        if spell is None:
            return False
        card = getattr(spell, "source", spell)
        card_types = getattr(card, "card_types", set())
        return CardType.INSTANT in card_types or CardType.SORCERY in card_types

    def _pump_effect(g: "GameState") -> None:
        if CardType.CREATURE not in source.card_types:
            return
        # Apply a +1/+0 until EOT continuous effect.
        source.modified_power = getattr(source, "modified_power", 2) + 1

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_pump_condition,
            effect=_pump_effect,
            source=source,
            controller=ctrl,
        )
    )

    # Register EOT trigger to reset the power back to base.
    def _eot_condition(g: Any, event: Any) -> bool:
        return True

    def _eot_effect(g: "GameState") -> None:
        if CardType.CREATURE in source.card_types:
            source.modified_power = 2  # reset to base

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=EndStepTriggeredEvent,
            condition=_eot_condition,
            effect=_eot_effect,
            source=source,
            controller=ctrl,
        )
    )
