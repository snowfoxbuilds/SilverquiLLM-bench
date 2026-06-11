"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}
_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


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
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard '
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._animated: bool = False

    # ------------------------------------------------------------------
    # Creature characteristics — exist only once animated, so that
    # hasattr-based checks (SBAs, combat eligibility) ignore the
    # unanimated land.
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("power")
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("toughness")
        return (
            self.modified_toughness
            + self.plus_one_counters
            - self.minus_one_counters
        )

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        if self._animated:
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    def register_triggers(self, game: GameState) -> None:
        # Called on battlefield entry: a permanent that re-enters the
        # battlefield is a new object, so any prior animation is forgotten.
        if self._animated:
            self._deanimate()

    def _deanimate(self) -> None:
        self._animated = False
        self.card_types.discard(CardType.CREATURE)
        self._original_card_types = frozenset(
            self._original_card_types - {CardType.CREATURE}
        )
        self.subtypes.discard("Wizard")
        for attr in (
            "base_power",
            "base_toughness",
            "modified_power",
            "modified_toughness",
            "damage_marked",
            "summoning_sick",
            "is_attacking",
            "is_blocking",
            "plus_one_counters",
            "minus_one_counters",
            "_base_plus_one_counters",
            "_base_minus_one_counters",
            "dealt_deathtouch_damage",
        ):
            if attr in self.__dict__:
                del self.__dict__[attr]

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

        def _colorless(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_life_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None or controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _any_color_restricted(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            try:
                choice = controller.choose(list(_COLORS), "choose a color of mana to add")
            except Exception:
                choice = _COLORS[0]
            if choice not in _COLORS:
                choice = _COLORS[0]
            controller.mana_pool.add_restricted(choice, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_life_cost,
                mana_produced=_any_color_restricted,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5} animation — activated ability (uses the stack)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _effect(game: GameState) -> None:
            if CardType.CREATURE in source.card_types:
                return
            source._animate(game)

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

    def _animate(self, game: GameState) -> None:
        """Become a 2/4 Wizard creature in place (still a land)."""
        self._animated = True
        self.card_types.add(CardType.CREATURE)
        # Update the original-characteristics snapshot so continuous-effect
        # recalculation does not strip the (duration-less) animation.
        self._original_card_types = frozenset(
            self._original_card_types | {CardType.CREATURE}
        )
        self.subtypes.add("Wizard")
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        # The land has been on the battlefield; summoning sickness is not
        # tracked for it (deliberate simplification).
        self.summoning_sick = False
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.dealt_deathtouch_damage = False
        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: GameState) -> None:
        """Whenever you cast an instant/sorcery, +1/+0 until end of turn."""
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_END_OF_TURN,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            return card is not None and bool(
                _SPELL_TYPES & getattr(card, "card_types", set())
            )

        def _effect(g: GameState) -> None:
            def _apply(g2: Any) -> None:
                for p in g2.players:
                    if g2.get_battlefield(p).contains(source):
                        source.modified_power += 1
                        return

            g.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            # Recalculate now so the pump is immediately observable.
            g.effect_manager.apply_all(g)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
