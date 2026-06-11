"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}
_ANY_COLOR = [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN]


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color.  Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn."  It's still a land.

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

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None or getattr(src, "is_tapped", False) or ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_restricted(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            color = ctrl.choose(_ANY_COLOR, "Choose a color (instant/sorcery only)")
            if color not in _ANY_COLOR:
                color = ManaType.WHITE
            ctrl.mana_pool.add(color, 1, restricted=True)

        return [
            ManaAbility(cost=_tap, mana_produced=_add_colorless, description="{T}: Add {C}."),
            ManaAbility(
                cost=_tap_pay_life,
                mana_produced=_add_any_restricted,
                description="{T}, Pay 1 life: Add one mana of any color "
                "(instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            cost = ManaCost(generic=5)
            # Restricted mana cannot pay for an ability (it's not a spell cast).
            if not ctrl.mana_pool.can_pay(cost, instant_or_sorcery=False):
                return False
            return ctrl.mana_pool.pay(cost, instant_or_sorcery=False)

        def _effect(game: "GameState") -> None:
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: Becomes a 2/4 Wizard creature (still a land).",
            )
        ]

    # ------------------------------------------------------------------
    # Animation (card-local in-place mutation — it stays a land)
    # ------------------------------------------------------------------

    def _animate(self, game: "GameState") -> None:
        # Gate: only animate if it isn't already a creature.
        if CardType.CREATURE in self.card_types:
            return

        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        # Creature characteristics (the land had none until now).
        self.base_power = 2
        self.base_toughness = 4
        self.power = 2
        self.toughness = 4
        self.damage_marked = 0
        self.summoning_sick = False  # has been on the battlefield
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.is_token = False
        self.dealt_deathtouch_damage = False

        # The animation is permanent — bake the creature type into the
        # continuous-effect reset snapshot so apply_all() doesn't strip it.
        self._original_card_types = frozenset(self.card_types)
        self._original_keywords = self.keywords

        land = self

        def _reset_anim() -> None:
            # Land-creature P/T reset (restores base before pumps reapply).
            land.card_types = set(land._original_card_types)
            land.keywords = land._original_keywords
            land.power = land.base_power
            land.toughness = land.base_toughness

        # Override per-instance so EffectManager.apply_all() resets our P/T.
        self._reset_characteristics = _reset_anim

        self._register_pump(game)

    def _register_pump(self, game: "GameState") -> None:
        """Register: whenever you cast an instant/sorcery, +1/+0 until EOT."""
        from engine.triggers import TriggerRegistration
        from engine.events import SpellCastTriggeredEvent
        from engine.continuous_effects import (
            ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer,
        )

        land = self

        def _condition(g: "GameState", event: Any) -> bool:
            ctrl = land.controller
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            if CardType.CREATURE not in land.card_types:
                return False
            if not g.get_battlefield(ctrl).contains(land):
                return False
            spell_obj = getattr(event, "spell", None)
            card = getattr(spell_obj, "source", None) or getattr(event, "card", None)
            return bool(card and (getattr(card, "card_types", set()) & _SPELL_TYPES))

        def _effect(g: "GameState") -> None:
            def _pump(gg: "GameState") -> None:
                land.power = getattr(land, "power", land.base_power) + 1

            g.effect_manager.add(ContinuousEffect(
                source=land, layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT, apply=_pump,
                duration=DURATION_END_OF_TURN,
            ))
            # Recompute now so the pump is observable immediately (the engine
            # otherwise only recalculates continuous effects at cleanup).
            g.effect_manager.apply_all(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller or game.active_player,
            )
        )
