"""Card implementation for Great Hall of the Biblioplex (SOS 257)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land (SOS 257).

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
      an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
      'Whenever you cast an instant or sorcery spell, this creature gets
      +1/+0 until end of turn.' It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature "
            "with 'Whenever you cast an instant or sorcery spell, this creature gets "
            "+1/+0 until end of turn.' It's still a land.",
        )
        super().__init__(**kwargs)
        # Creature stats — set when {5} ability transforms the land
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        # ---- Ability 1: {T} → Add {C} ----
        def _tap_cost_colorless(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _produce_colorless(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        ability_colorless = ManaAbility(
            cost=_tap_cost_colorless,
            mana_produced=_produce_colorless,
            description="{T}: Add {C}.",
        )

        # ---- Ability 2: {T}, Pay 1 life → Add one mana of any color ----
        # UNVERIFIED: mana restricted to instant/sorcery casting not enforceable — engine lacks conditional mana tags
        def _tap_and_life_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller = source.controller
            if controller is not None:
                controller.life -= 1
            return True

        def _produce_colored(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            # Try to get a color choice from the player's script; default to WHITE
            from engine.player import DeterministicPlayer
            chosen: ManaType = ManaType.WHITE
            if isinstance(controller, DeterministicPlayer) and controller._script:
                choice = controller._script.popleft()
                if isinstance(choice, ManaType) and choice != ManaType.COLORLESS:
                    chosen = choice
            controller.mana_pool.add(chosen, 1)

        ability_colored = ManaAbility(
            cost=_tap_and_life_cost,
            mana_produced=_produce_colored,
            description="{T}, Pay 1 life: Add one mana of any color.",
        )

        return [ability_colorless, ability_colored]

    # ------------------------------------------------------------------
    # Activated ability: {5} → become 2/4 Wizard creature (still land)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _five_cost(game: Any, src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            # Pay {5} — 5 generic mana (any color)
            pool = controller.mana_pool
            total_available = pool.total()
            if total_available < 5:
                return False
            # Drain 5 mana from the pool in any order
            remaining = 5
            for mana_type in [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
                ManaType.COLORLESS,
            ]:
                if remaining <= 0:
                    break
                available = pool.get(mana_type)
                spent = min(available, remaining)
                if spent > 0:
                    from engine.mana import ManaPool
                    pool._pool[mana_type] = available - spent
                    remaining -= spent
            return True

        def _five_effect(game: Any) -> None:
            # Only transform if not already a creature
            if CardType.CREATURE in source.card_types:
                return
            # Become a 2/4 Wizard creature (still a land)
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            # Register the pump trigger
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_five_cost,
                effect=_five_effect,
                description="{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature.",
            )
        ]

    def _register_pump_trigger(self, game: Any) -> None:
        """Register the 'whenever you cast an instant or sorcery, +1/+0' trigger."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = source.controller or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            # Only trigger for instants or sorceries cast by the controller
            if getattr(event, "player", None) is not controller:
                return False
            card = getattr(event, "card", None) or getattr(event, "spell", None)
            if card is None:
                return False
            card_types = getattr(card, "card_types", set())
            is_instant = CardType.INSTANT in card_types
            is_sorcery = CardType.SORCERY in card_types
            if not (is_instant or is_sorcery):
                return False
            return True

        def _effect(game: Any) -> None:
            # UNVERIFIED: +1/+0 until end of turn expiry — EOT cleanup integration not tested
            source.modified_power += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
