"""Card implementation for Great Hall of the Biblioplex.

Oracle text:
  {T}: Add {C}.
  {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
      an instant or sorcery spell.
  {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
      "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
      until end of turn." It's still a land.

Sub-mechanics:
  (a) Two mana abilities: unrestricted colorless, restricted any-color.
  (b) Persistent animation ({5} activation, no end-of-turn cleanup).
  (c) Prowess-like spell-cast trigger granting +1/+0 until end of turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land (rare, SOS #257).

    Implements three sub-mechanics:
    (a) Two mana abilities (colorless unrestricted, any-color restricted).
    (b) Persistent animation to 2/4 Wizard creature.
    (c) Prowess-like spell-cast trigger (+1/+0 until end of turn).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault("card_types", {CardType.LAND})
        kwargs.setdefault("rules_text",
            '{T}: Add {C}.\n'
            '{T}, Pay 1 life: Add one mana of any color. Spend this mana only '
            'to cast an instant or sorcery spell.\n'
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard creature '
            'with "Whenever you cast an instant or sorcery spell, this creature gets '
            '+1/+0 until end of turn." It\'s still a land.')
        super().__init__(**kwargs)

        # Animation state — persistent until leaves play
        self._is_animated: bool = False
        # Power/toughness for animated form
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        # Temporary boost tracking (until end of turn)
        self._power_boost: int = 0
        # Summoning sickness (relevant when animated)
        self.summoning_sick: bool = False

    # ------------------------------------------------------------------
    # (a) Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the two mana abilities."""
        return [
            ManaAbility(
                cost=self._tap_cost,
                mana_produced=self._produce_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=self._tap_and_life_cost,
                mana_produced=self._produce_any_color_restricted,
                description="{T}, Pay 1 life: Add one mana of any color (instant/sorcery only).",
            ),
        ]

    def _tap_cost(self, game: Any = None, source: Any = None) -> bool:
        """Check/pay tap cost."""
        if self.is_tapped:
            return False
        self.is_tapped = True
        return True

    def _tap_and_life_cost(self, game: Any = None, source: Any = None) -> bool:
        """Check/pay tap + 1 life cost."""
        if self.is_tapped:
            return False
        controller = getattr(self, "controller", None)
        if controller is None:
            return False
        if controller.life < 1:
            return False
        self.is_tapped = True
        controller.life -= 1
        return True

    def _produce_colorless(self, game: Any = None) -> dict[str, Any]:
        """Produce one colorless mana (unrestricted)."""
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.mana_pool.add(ManaType.COLORLESS, 1)
        return {"type": ManaType.COLORLESS, "amount": 1}

    def _produce_any_color_restricted(self, game: Any = None) -> dict[str, Any]:
        """Produce one mana of any color, restricted to instant/sorcery spells.

        Uses the engine's restricted-mana primitive via ManaPool.add_restricted().
        Read restrictions back via `controller.mana_pool.restricted_mana`.
        """
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.mana_pool.add_restricted(
                ManaType.COLORLESS, 1,
                restriction="instant_or_sorcery",
                source=self,
            )
        return {"type": "any_color", "amount": 1, "restriction": "instant_or_sorcery"}

    # ------------------------------------------------------------------
    # (b) Persistent animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the {5} animation ability.

        {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
        with the prowess-like trigger.  It's still a land.  Persistent (no
        end-of-turn cleanup); the effect is a no-op if the land is already a
        creature.
        """

        def _cost(game: Any, source: Any = None) -> bool:
            controller = getattr(self, "controller", None)
            if controller is None or controller.mana_pool.total() < 5:
                return False
            return bool(controller.mana_pool.pay(ManaCost(generic=5)))

        def _effect(game: Any) -> None:
            # Gate: no-op if already a creature.
            if CardType.CREATURE in self.card_types:
                return
            self._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with \"Whenever you cast an instant or "
                    "sorcery spell, this creature gets +1/+0 until end of "
                    "turn.\" It's still a land."
                ),
            )
        ]

    def _animate(self, game: Any) -> None:
        """Apply persistent animation — become 2/4 Wizard creature."""
        self._is_animated = True
        self.card_types.add(CardType.CREATURE)
        self.subtypes.add("Wizard")
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self._power_boost = 0
        # Summoning sickness applies when becoming a creature
        self.summoning_sick = True
        # Register the spell-cast trigger
        self._register_prowess_trigger(game)

    def _deanimate(self) -> None:
        """Remove animation — revert to just a land."""
        self._is_animated = False
        self.card_types.discard(CardType.CREATURE)
        self.subtypes.discard("Wizard")
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0
        self._power_boost = 0

    # ------------------------------------------------------------------
    # (c) Prowess-like spell-cast trigger
    # ------------------------------------------------------------------

    def _register_prowess_trigger(self, game: Any) -> None:
        """Register: Whenever you cast an instant or sorcery, +1/+0 until EOT."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None)
        if controller is None:
            return

        def _condition(game: Any, event: Any) -> bool:
            # Only fire if source is still a creature
            if CardType.CREATURE not in source.card_types:
                return False
            # Controller-only
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not ctrl:
                return False
            # Must be instant or sorcery
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            spell_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in spell_types and CardType.SORCERY not in spell_types:
                return False
            return True

        def _effect(game: Any) -> None:
            # +1/+0 until end of turn
            source._power_boost += 1
            source.modified_power = source.base_power + source._power_boost

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def register_triggers(self, game: Any) -> None:
        """Register triggers if animated (called when entering battlefield)."""
        if self._is_animated:
            self._register_prowess_trigger(game)

    # ------------------------------------------------------------------
    # Properties for power/toughness
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Current power including boosts."""
        if not self._is_animated:
            return 0
        return self.modified_power

    @property
    def toughness(self) -> int:
        """Current toughness."""
        if not self._is_animated:
            return 0
        return self.modified_toughness

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
        """Override to preserve persistent animation through effect resets.

        The engine's effect_manager.apply_all() calls _reset_characteristics()
        on all permanents during cleanup. We must re-apply animation state
        after the base reset so it persists across turns.
        """
        super()._reset_characteristics()
        if self._is_animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")

    def on_resolve(self, game: Any) -> None:
        """Lands don't resolve from the stack — no-op for safety."""
        pass

    def end_of_turn_cleanup(self) -> None:
        """Remove +1/+0 boosts at end of turn (only the boost, not animation)."""
        self._power_boost = 0
        if self._is_animated:
            self.modified_power = self.base_power

    def on_leave_battlefield(self, game: Any = None) -> None:
        """When leaving play, clear animation state."""
        self._deanimate()
        # Unregister triggers
        if game is not None and hasattr(game, "trigger_manager"):
            game.trigger_manager.unregister(self)

