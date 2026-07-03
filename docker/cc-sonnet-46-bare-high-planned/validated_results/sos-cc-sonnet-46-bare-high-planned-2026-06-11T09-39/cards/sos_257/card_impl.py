"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _tap_cost(game: Any, source: Any) -> bool:
    """Standard {T} cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


def _tap_and_spend_life(game: Any, source: Any) -> bool:
    """{T}, Pay 1 life cost."""
    if getattr(source, "is_tapped", False):
        return False
    controller = source.controller
    if controller is None or controller.life <= 1:
        return False
    source.is_tapped = True
    controller.life -= 1
    return True


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

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
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. "
            "Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Animation state: tracks current modified power from pump.
        self._animated_base_power: int = 2

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _add_restricted(game: Any) -> None:
            """Add one mana of any color, restricted to instant/sorcery."""
            controller = source.controller
            if controller is None:
                return
            colors = [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN]
            try:
                chosen = controller.choose(colors, "Choose a color for the restricted mana")
            except Exception:
                chosen = ManaType.COLORLESS
            if chosen not in colors:
                chosen = ManaType.COLORLESS
            # Add restricted: use colorless as a proxy tracked by _restricted_colorless.
            # Deliberate limitation: we store the color choice but enforce restriction via
            # the colorless restricted tracking in ManaPool.
            if chosen == ManaType.COLORLESS:
                controller.mana_pool.add_restricted(ManaType.COLORLESS, 1)
            else:
                # Add 1 of the chosen color AND mark 1 restricted so the pool can't
                # use it for non-instant/sorcery (as a best-effort signal).
                controller.mana_pool.add(chosen, 1)
                # Track restriction via a separate counter on the pool.
                if not hasattr(controller.mana_pool, "_restricted_colored"):
                    controller.mana_pool._restricted_colored = 0
                controller.mana_pool._restricted_colored += 1

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_spend_life,
                mana_produced=_add_restricted,
                description="{T}, Pay 1 life: Add one mana of any color (instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability: {5} — animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: Any, src: Any) -> bool:
            """Pay {5} generic mana. Gate on not already a creature."""
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if CardType.CREATURE in src.card_types:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _animate_effect(game: Any) -> None:
            """Become a 2/4 Wizard creature (still a land). Register pump trigger."""
            if CardType.CREATURE in source.card_types:
                return

            # Mutate in place — add Creature type, P/T, subtype.
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            source._animated_base_power = 2
            # No summoning sickness — already been on battlefield.
            source.summoning_sick = False
            source.damage_marked = 0

            # Register pump trigger and EOT reset.
            _register_pump_trigger(game, source)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: Become a 2/4 Wizard creature until end of turn (still a land).",
            )
        ]


def _register_pump_trigger(game: "GameState", source: Any) -> None:
    """Register +1/+0 until EOT trigger and EOT reset for the animated Hall."""
    from engine.triggers import TriggerRegistration

    controller = source.controller

    def _cast_condition(game: Any, event: Any) -> bool:
        if event.controller is not source.controller:
            return False
        card = event.card
        if card is None:
            return False
        types = getattr(card, "card_types", set())
        return CardType.INSTANT in types or CardType.SORCERY in types

    def _pump_effect(game: Any) -> None:
        """Apply +1/+0 until end of turn."""
        source._animated_base_power += 1
        source.modified_power = source._animated_base_power

    def _eot_condition(game: Any, event: Any) -> bool:
        return True

    def _eot_effect(game: Any) -> None:
        """Reset pump at end of turn."""
        source._animated_base_power = 2
        source.modified_power = 2

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_cast_condition,
            effect=_pump_effect,
            source=source,
            controller=controller,
        )
    )
    game.trigger_manager.register(
        TriggerRegistration(
            event_type=EndStepTriggeredEvent,
            condition=_eot_condition,
            effect=_eot_effect,
            source=source,
            controller=controller,
        )
    )
