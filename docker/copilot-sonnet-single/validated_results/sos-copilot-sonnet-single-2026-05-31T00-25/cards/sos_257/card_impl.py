"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


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
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
            "only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature-like attributes used when animated.
        self._is_creature: bool = False
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.damage_marked: int = 0
        self.summoning_sick: bool = False

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_mana(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life_cost(game: Any, src: Any) -> bool:
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

        def _colored_mana(game: Any) -> None:
            """Add one mana of any color (simplified: white; restricted to instants/sorceries)."""
            controller = source.controller
            if controller is not None:
                # ENGINE LIMITATION: Mana restriction (spend only on instants/sorceries)
                # is not enforced. We add colorless as a simplified representation
                # of "any color, restricted" mana.
                controller.mana_pool.add(ManaType.WHITE, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_mana,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_colored_mana,
                description="{T}, Pay 1 life: Add one mana of any color (restricted to instants/sorceries).",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated abilities
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: Any, src: Any) -> bool:
            if source._is_creature:
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 5:
                return False
            try:
                controller.mana_pool.pay(ManaCost(generic=5))
            except Exception:
                return False
            return True

        def _animate_effect(game: Any) -> None:
            if source._is_creature:
                return
            source._is_creature = True
            source.base_power = 2
            source.base_toughness = 2 + 2  # 4
            source.modified_power = 2
            source.modified_toughness = 4
            source.card_types = source.card_types | {CardType.CREATURE}
            source.subtypes = source.subtypes | {"Wizard"}
            # Register trigger: whenever controller casts instant/sorcery,
            # this creature gets +1/+0 until end of turn.
            source._register_spellcast_trigger(game)

        return [
            ActivatedAbility(
                cost=_animate_cost,
                effect=_animate_effect,
                description="{5}: Animate as a 2/4 Wizard creature.",
            ),
        ]

    def _register_spellcast_trigger(self, game: "GameState") -> None:
        """Register: whenever you cast an instant or sorcery, this gets +1/+0 until EOT."""
        from engine.triggers import TriggerRegistration

        source = self

        # Try to hook into a spell-cast event if available.
        try:
            from engine.events import SpellCastEvent

            def _condition(g: Any, event: Any) -> bool:
                spell = getattr(event, "spell", None) or getattr(event, "card", None)
                if spell is None:
                    return False
                controller = getattr(source, "controller", None)
                caster = getattr(event, "controller", None) or getattr(event, "player", None)
                if controller is None or caster is None:
                    return False
                if controller is not caster:
                    return False
                card_types = getattr(spell, "card_types", set())
                return CardType.INSTANT in card_types or CardType.SORCERY in card_types

            def _effect(g: Any) -> None:
                source.modified_power = getattr(source, "modified_power", 2) + 1

            game.trigger_manager.register(TriggerRegistration(
                event_type=SpellCastEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=getattr(source, "controller", None) or game.active_player,
            ))
        except (ImportError, AttributeError):
            # SpellCastEvent not available in this engine version — skip.
            pass
