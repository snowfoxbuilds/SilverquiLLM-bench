"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """{T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color (instant/sorcery only).
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature-land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to "
            "cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature "
            "with \"Whenever you cast an instant or sorcery spell, this creature "
            "gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        # Power/toughness — only relevant after becoming a creature
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.subtypes: set[str] = set()
        # Track whether a spell-cast trigger has been registered
        self._spell_trigger_registered: bool = False

    # -----------------------------------------------------------------------
    # Mana abilities
    # -----------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        # Ability 1: {T}: Add {C}
        def _colorless_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_mana(game: Any) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        # Ability 2: {T}, Pay 1 life: Add one mana of any color
        def _colored_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.life -= 1
            return True

        def _colored_mana(game: Any) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # Choose a color
            color_options = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            try:
                chosen = controller.choose(color_options, "Choose a color of mana to add")
            except Exception:
                chosen = ManaType.COLORLESS
            if chosen not in color_options:
                chosen = ManaType.COLORLESS
            controller.mana_pool.add(chosen, 1)
            # UNVERIFIED: mana spending restriction — engine does not enforce spend-only-on-instant/sorcery

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

    # -----------------------------------------------------------------------
    # Activated ability: {5}
    # -----------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _creature_cost(game: Any, src: Any) -> bool:
            # "If this land isn't a creature" — no-op (fail cost) if already a creature
            if CardType.CREATURE in getattr(src, "card_types", set()):
                return False
            controller = getattr(src, "controller", None)
            if controller is None:
                # Try via src
                return False
            # Requires {5} generic mana
            if controller.mana_pool.total() < 5:
                return False
            controller.mana_pool.pay(ManaCost(generic=5))
            return True

        def _creature_effect(game: Any) -> None:
            # Become a 2/4 Wizard creature — still a land
            source.card_types = (getattr(source, "card_types", set()) or set()) | {CardType.CREATURE}
            source.subtypes = (getattr(source, "subtypes", set()) or set()) | {"Wizard"}
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            # Now that the card has CREATURE in card_types, register the spell-cast trigger.
            # (register_triggers early-returns when called at ETB because it's still a land then.)
            source.register_triggers(game)

        return [
            ActivatedAbility(
                cost=_creature_cost,
                effect=_creature_effect,
                description="{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature-land.",
            )
        ]

    # -----------------------------------------------------------------------
    # Triggered ability — Whenever you cast an instant or sorcery, +1/+0
    # -----------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register spell-cast trigger only if this card is currently a creature."""
        if CardType.CREATURE not in getattr(self, "card_types", set()):
            return

        if self._spell_trigger_registered:
            return

        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            # Must be instant or sorcery
            spell = getattr(event, "spell", None)
            if spell is None:
                return False
            spell_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in spell_types and CardType.SORCERY not in spell_types:
                return False
            # Must be cast by the controller of this permanent
            src_ctrl = getattr(source, "controller", None)
            event_ctrl = getattr(event, "controller", None) or getattr(event, "player", None)
            if src_ctrl is None or event_ctrl is None:
                return False
            return src_ctrl is event_ctrl

        def _effect(game: Any) -> None:
            # +1/+0 until end of turn
            # UNVERIFIED: "+1/+0 until end of turn revert" — no continuous effect system for EOT cleanup
            source.modified_power = getattr(source, "modified_power", 0) + 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
        self._spell_trigger_registered = True
