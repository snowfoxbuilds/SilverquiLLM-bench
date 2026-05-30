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
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_ANY_COLOR: tuple[ManaType, ...] = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


def _on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if player.zones[Zone.BATTLEFIELD].contains(obj):
            return True
    return False


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.

    Until the ``{5}`` ability animates it, the land deliberately exposes no
    ``base_power``/``power``/``toughness`` characteristics so that the
    engine's ``hasattr``-based creature checks (combat eligibility,
    toughness state-based actions) correctly ignore it.
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
        self.colors: list[str] = []
        self._animated: bool = False
        self._pump_trigger_registered: bool = False

    # ------------------------------------------------------------------
    # Creature characteristics — only meaningful once animated
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
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        # Re-apply the animation's type/P-T base each effect-recalculation
        # cycle so that the creature state survives ``EffectManager.apply_all``.
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = self._base_plus_one_counters
            self.minus_one_counters = self._base_minus_one_counters

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap(game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: GameState, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_any_color(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            color = controller.choose(list(_ANY_COLOR), "Choose a color of mana")
            if color not in _ANY_COLOR:
                color = ManaType.COLORLESS
            controller.mana_pool.add(color, 1)

        return [
            ManaAbility(
                cost=_tap,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life,
                mana_produced=_add_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability — {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: GameState) -> None:
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
        if self._animated or CardType.CREATURE in self.card_types:
            return  # Already a creature — the ability does nothing.
        self._animated = True
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.damage_marked = 0
        self.summoning_sick = False
        self.is_attacking = False
        self.is_blocking = False
        self.dealt_deathtouch_damage = False
        self.card_types.add(CardType.CREATURE)
        self.subtypes.add("Wizard")
        self._register_pump_trigger(game)

    def _register_pump_trigger(self, game: GameState) -> None:
        if self._pump_trigger_registered:
            return
        self._pump_trigger_registered = True
        source = self

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            if not source._animated:
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            if not _on_battlefield(game, source):
                return False
            if event.controller is not source.controller:
                return False
            return _is_instant_or_sorcery(event.card)

        def _effect(game: GameState) -> None:
            if not source._animated or not _on_battlefield(game, source):
                return

            def _bump(g: GameState) -> None:
                source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_bump,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=source.controller,
            )
        )
