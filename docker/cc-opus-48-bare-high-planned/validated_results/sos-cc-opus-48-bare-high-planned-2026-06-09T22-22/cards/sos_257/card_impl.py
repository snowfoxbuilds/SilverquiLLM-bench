"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _tap_cost(game: "GameState", source: Any) -> bool:
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an
    instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. Spend "
            "this mana only to cast an instant or sorcery spell.\n{5}: If this "
            "land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature gets '
            '+1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._eot_pump: int = 0

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: "GameState") -> None:
            if source.controller is not None:
                source.controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_cost(game: "GameState", src: Any) -> bool:
            # {T}, Pay 1 life.
            if getattr(src, "is_tapped", False):
                return False
            ctrl = src.controller
            if ctrl is None or ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_color(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            color_options = [
                ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                ManaType.RED, ManaType.GREEN,
            ]
            try:
                chosen = ctrl.choose(color_options, "Choose a color of mana")
            except Exception:
                chosen = ManaType.BLUE
            if chosen not in color_options:
                chosen = ManaType.BLUE
            # Restricted: only spendable on an instant or sorcery spell.
            ctrl.mana_pool.add(chosen, 1, restricted=True)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_any_color_cost,
                mana_produced=_add_any_color,
                description="{T}, Pay 1 life: Add one mana of any color "
                "(instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability — {5} animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            # Not casting a spell — instant/sorcery-restricted mana may not pay.
            return ctrl.mana_pool.pay(ManaCost(generic=5), for_instant_or_sorcery=False)

        def _animate(game: "GameState") -> None:
            # Gate: only if not already a creature.
            if CardType.CREATURE in source.card_types:
                return
            source._become_creature(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description="{5}: Becomes a 2/4 Wizard creature; still a land.",
            )
        ]

    # ------------------------------------------------------------------
    # Animation helper (card-local; mutates in place — stays a land)
    # ------------------------------------------------------------------

    def _become_creature(self, game: "GameState") -> None:
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        # Plain creature-combat attributes (Land is not a Creature subclass).
        self.base_power = 2
        self.base_toughness = 4
        self.power = 2
        self.toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.summoning_sick = False  # has been on the battlefield
        self.is_attacking = False
        self.is_blocking = False
        self.is_token = False
        self._eot_pump = 0
        # Bake the animated baseline into the characteristic snapshot so the
        # continuous-effect reset (cleanup) does NOT de-animate it — the
        # animation is permanent, not until-end-of-turn.
        self._original_card_types = frozenset(self.card_types)
        self._original_keywords = self.keywords

        from engine.triggers import TriggerRegistration

        ctrl = self.controller

        # Granted ability: whenever you cast an instant/sorcery, +1/+0 EOT.
        def _pump_condition(game: Any, event: Any) -> bool:
            if CardType.CREATURE not in self.card_types:
                return False
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not self.controller:
                return False
            spell = getattr(event, "card", None)
            types = getattr(spell, "card_types", set())
            return bool(types & {CardType.INSTANT, CardType.SORCERY})

        def _pump_effect(game: Any) -> None:
            self._eot_pump += 1
            self.power = self.base_power + self._eot_pump

        # Reset the until-end-of-turn pump at the end step.
        def _reset_effect(game: Any) -> None:
            self._eot_pump = 0
            if CardType.CREATURE in self.card_types:
                self.power = self.base_power

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_pump_condition,
                effect=_pump_effect,
                source=self,
                controller=ctrl,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=lambda g, e: True,
                effect=_reset_effect,
                source=self,
                controller=ctrl,
            )
        )
