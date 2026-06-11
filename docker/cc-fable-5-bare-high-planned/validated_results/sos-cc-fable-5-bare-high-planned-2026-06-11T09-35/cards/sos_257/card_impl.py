"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLORS: list[ManaType] = [
    ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
    ManaType.RED, ManaType.GREEN,
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
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._animated: bool = False

    # ------------------------------------------------------------------
    # Power/toughness — only exist while animated (so SBAs and combat
    # ignore the unanimated land).
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("not a creature")
        return (
            self.modified_power
            + self.plus_one_counters
            - self.minus_one_counters
        )

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("not a creature")
        return (
            self.modified_toughness
            + self.plus_one_counters
            - self.minus_one_counters
        )

    def _reset_characteristics(self) -> None:
        """Reset for effect recalculation; keep the animated base 2/4."""
        super()._reset_characteristics()
        if self._animated:
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            if source.controller is not None:
                source.controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_life_cost(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None or getattr(src, "is_tapped", False):
                return False
            if controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            color = controller.choose(list(_COLORS), "Choose a color of mana")
            if color not in _COLORS:
                color = _COLORS[0]
            controller.mana_pool.add_restricted(color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_life_cost,
                mana_produced=_add_restricted_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost.parse("{5}"))

        def _effect(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — no effect
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
            ),
        ]

    def _animate(self, game: "GameState") -> None:
        """Become a 2/4 Wizard creature (still a land), in place."""
        from engine.continuous_effects import (
            ContinuousEffect,
            DURATION_END_OF_TURN,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        self._animated = True
        self.card_types.add(CardType.CREATURE)
        # The type change has no duration — survive effect recalculation.
        self._original_card_types = frozenset(self.card_types)
        self.subtypes.add("Wizard")
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.is_attacking = False
        self.is_blocking = False
        self.dealt_deathtouch_damage = False
        self.is_token = False

        def _condition(game: Any, event: Any) -> bool:
            ctrl = source.controller
            if ctrl is None or event.controller is not ctrl:
                return False
            return bool(
                getattr(event.card, "card_types", set())
                & {CardType.INSTANT, CardType.SORCERY}
            )

        def _pump(game: "GameState") -> None:
            def _on_battlefield(g: Any) -> bool:
                for p in g.players:
                    if g.get_battlefield(p).contains(source):
                        return True
                return False

            if not _on_battlefield(game):
                return
            # Apply now and register an until-EOT effect so recalculation
            # (cleanup's apply_all) stays consistent.
            source.modified_power += 1

            def _apply(g: Any) -> None:
                if _on_battlefield(g):
                    source.modified_power += 1

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            ))

        controller = self.controller or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_pump,
            source=self,
            controller=controller,
        ))
