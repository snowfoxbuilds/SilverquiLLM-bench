"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLORS = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


def _instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return bool(types & {CardType.INSTANT, CardType.SORCERY})


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    ``{T}: Add {C}``.
    ``{T}, Pay 1 life: Add one mana of any color.  Spend this mana only to
    cast an instant or sorcery spell.``
    ``{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature gets
    +1/+0 until end of turn."  It's still a land.``

    SOS collector number 257.

    The "spend this mana only to cast an instant or sorcery" restriction is a
    known engine simplification — the mana pool carries no restriction tags,
    so the colored mana is produced unrestricted.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        self._animated: bool = False

    # ------------------------------------------------------------------
    # Animated (creature) characteristics
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("power")
        return (
            self.modified_power
            + self.plus_one_counters
            - self.minus_one_counters
        )

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("toughness")
        return (
            self.modified_toughness
            + self.plus_one_counters
            - self.minus_one_counters
        )

    def _animate(self) -> None:
        """Turn the land into a 2/4 Wizard creature (it stays a land)."""
        self._animated = True
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.damage_marked = 0
        self.is_attacking = False
        self.is_blocking = False
        self.is_token = False
        self.dealt_deathtouch_damage = False
        # A land already in play is not summoning sick as a creature.
        self.summoning_sick = False

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        if self._animated:
            # The type change persists across continuous-effect recomputes.
            self.card_types = set(self.card_types) | {CardType.CREATURE}
            self.subtypes = set(self.subtypes) | {"Wizard"}
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = self._base_plus_one_counters
            self.minus_one_counters = self._base_minus_one_counters

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost_tap(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _produce_colorless(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _cost_tap_life(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _produce_any(game: Any) -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            color = ctrl.choose(list(_COLORS), "Choose a color")
            ctrl.mana_pool.add(color, 1)

        return [
            ManaAbility(
                cost=_cost_tap,
                mana_produced=_produce_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_cost_tap_life,
                mana_produced=_produce_any,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability — {5}: become a creature
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list:
        from engine.card import ActivatedAbility

        source = self

        def _cost(game: Any, src: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            return bool(ctrl.mana_pool.pay(ManaCost.parse("{5}")))

        def _effect(game: Any) -> None:
            if CardType.CREATURE in source.card_types:
                return
            source._animate()

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: If this land isn't a creature, it becomes a "
                "2/4 Wizard creature. It's still a land.",
            )
        ]

    # ------------------------------------------------------------------
    # Triggered ability — +1/+0 on instant/sorcery cast while animated
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.continuous_effects import (
            DURATION_END_OF_TURN,
            ContinuousEffect,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            if not source._animated:
                return False
            if getattr(event, "controller", None) is not source.controller:
                return False
            return _instant_or_sorcery(getattr(event, "card", None))

        def _effect(game: "GameState") -> None:
            def _buff(game: Any) -> None:
                if source._animated:
                    source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_buff,
                    duration=DURATION_END_OF_TURN,
                )
            )

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
