"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _tap_cost(game: Any, source: Any) -> bool:
    """Standard tap cost: check not tapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

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
        self._animated: bool = False  # tracks whether animation is active

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _life_tap_cost(game: Any, src: Any) -> bool:
            """Tap + pay 1 life."""
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _restricted_color_effect(game: Any) -> None:
            """Add one restricted mana of any color (player chooses)."""
            controller = source.controller
            if controller is None:
                return
            color_options = [
                ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                ManaType.RED, ManaType.GREEN,
            ]
            try:
                chosen = controller.choose(color_options, "choose a color of mana")
            except Exception:
                chosen = ManaType.COLORLESS
            if chosen not in color_options:
                chosen = ManaType.COLORLESS
            controller.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_tap_cost,
                mana_produced=_restricted_color_effect,
                description="{T}, Pay 1 life: Add one mana of any color "
                            "(instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability: animate to 2/4 Wizard
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: Any, src: Any) -> bool:
            """Pay {5} generic."""
            if source._animated:
                return False  # already a creature; activation not allowed
            controller = src.controller
            if controller is None:
                return False
            cost = ManaCost.parse("{5}")
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _animate_effect(game: "GameState") -> None:
            """Animate to 2/4 Wizard; register permanent continuous effects."""
            if source._animated:
                return
            source._animated = True
            # Add Wizard subtype permanently (subtypes not reset by _reset_characteristics).
            source.subtypes = (getattr(source, "subtypes", set()) or set()) | {"Wizard"}

            # Permanent type-change effect (layer 4): add CREATURE type.
            def _apply_type(g: Any) -> None:
                source.card_types = source.card_types | {CardType.CREATURE}

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    sublayer=None,
                    apply=_apply_type,
                    duration=DURATION_PERMANENT,
                )
            )

            # Permanent P/T-setting effect (layer 7b): set to 2/4.
            def _apply_pt(g: Any) -> None:
                source.modified_power = 2
                source.modified_toughness = 4

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_apply_pt,
                    duration=DURATION_PERMANENT,
                )
            )

            # Apply effects immediately so the land shows as a creature right now.
            game.effect_manager.apply_all(game)

            # Register the pump trigger for instant/sorcery spells.
            _register_pump_trigger(game, source)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: Animate to 2/4 Wizard creature.",
            )
        ]


def _register_pump_trigger(game: "GameState", source: Any) -> None:
    """Register the SpellCastTriggeredEvent pump trigger on the animated land."""
    from engine.events import SpellCastTriggeredEvent
    from engine.triggers import TriggerRegistration

    def _condition(game: Any, event: Any) -> bool:
        ctrl = getattr(source, "controller", None)
        caster = getattr(event, "controller", None)
        if caster is not ctrl:
            return False
        card = getattr(event, "card", None)
        if card is None:
            return False
        return bool(
            getattr(card, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}
        )

    def _effect(game: "GameState") -> None:
        """Register a +1/+0 continuous effect until EOT."""
        def _apply(g: Any) -> None:
            # Only pump if still a creature.
            if CardType.CREATURE in getattr(source, "card_types", set()):
                source.modified_power = getattr(source, "modified_power", 2) + 1

        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            )
        )

    controller = getattr(source, "controller", None) or game.active_player
    game.trigger_manager.register(
        TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=source,
            controller=controller,
        )
    )
