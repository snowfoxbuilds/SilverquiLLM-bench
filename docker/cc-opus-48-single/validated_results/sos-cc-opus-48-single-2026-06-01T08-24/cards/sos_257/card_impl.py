"""Card implementation for Great Hall of the Biblioplex.

A green-phase utility land:

* ``{T}: Add {C}.``
* ``{T}, Pay 1 life: Add one mana of any color. Spend this mana only to
  cast an instant or sorcery spell.``
* ``{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
  with "Whenever you cast an instant or sorcery spell, this creature gets
  +1/+0 until end of turn." It's still a land.``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — a utility land that can animate.

    Power/toughness are exposed as plain attributes (the card is a
    :class:`~engine.card.Land`, not a :class:`~engine.card.Creature`, until
    animated).  While not a creature the printed P/T is irrelevant; once
    animated by the ``{5}`` ability it becomes a 2/4 Wizard with a
    prowess-style pump.
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
        # Animated-creature state. Base P/T only meaningful once animated.
        self._base_power: int = 2
        self._base_toughness: int = 4
        # +X/+0 until-end-of-turn bonus.  This is *recomputed* every time
        # ``EffectManager.apply_all`` runs: it is zeroed by
        # ``_reset_characteristics`` and then re-accumulated by each surviving
        # MODIFY_PT continuous effect registered by the prowess trigger.  Those
        # effects carry ``DURATION_END_OF_TURN`` so the engine's cleanup step
        # (``remove_expired`` + ``apply_all``) clears the bonus at end of turn.
        self._power_bonus: int = 0
        self._triggers_registered: bool = False
        self._animated: bool = False
        self._animation_effect_registered: bool = False

    # ------------------------------------------------------------------
    # Continuous-effect reset support
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics before continuous effects reapply.

        In addition to the base reset (card types / keywords), zero the
        until-end-of-turn power bonus so that ``EffectManager.apply_all`` is
        idempotent: the bonus is rebuilt from scratch by the surviving
        MODIFY_PT effects each recalculation.  When those effects expire at
        end of turn (``remove_expired``), the subsequent ``apply_all`` leaves
        the bonus at 0.
        """
        super()._reset_characteristics()
        self._power_bonus = 0

    # ------------------------------------------------------------------
    # Animated-creature power / toughness
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Current power (only meaningful while animated)."""
        return self._base_power + self._power_bonus

    @property
    def toughness(self) -> int:
        """Current toughness (only meaningful while animated)."""
        return self._base_toughness

    @property
    def is_creature(self) -> bool:
        return CardType.CREATURE in self.card_types

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_produced(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _anycolor_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            # Tap, then pay 1 life.
            src.is_tapped = True
            controller.life -= 1
            return True

        def _anycolor_produced(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            # Produce one mana of any color (choose green by default; a real
            # game would let the controller choose among the five colors).
            controller.mana_pool.add(ManaType.GREEN, 1)
            # UNVERIFIED: "Spend this mana only to cast an instant or sorcery
            # spell." — engine.mana.ManaPool stores only dict[ManaType, int]
            # with no concept of restricted/earmarked mana, and the casting
            # payment path is core and heavily tested. Adding a restricted-mana
            # facility that could enforce (and reject) this spend-restriction
            # cannot be done as a strict no-op-by-default change without risking
            # regressions in the mana/casting pipeline, so the restriction is
            # left unenforced. The any-color production and the 1-life payment
            # ARE modelled above.

        return [
            ManaAbility(
                cost=_colorless_cost,
                mana_produced=_colorless_produced,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_anycolor_cost,
                mana_produced=_anycolor_produced,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability — {5}: animate into a 2/4 Wizard
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            cost = ManaCost.parse("{5}")
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: Any) -> None:
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with prowess-style pump. It's still a land."
                ),
            ),
        ]

    def _animate(self, game: Any) -> None:
        """Turn the land into a 2/4 Wizard creature (no-op if already one)."""
        if CardType.CREATURE in self.card_types:
            # "If this land isn't a creature" — already animated; do nothing.
            return
        self.card_types.add(CardType.CREATURE)
        self.subtypes.add("Wizard")
        self._base_power = 2
        self._base_toughness = 4
        self._animated = True
        # It's still a land — LAND remains in card_types (never removed).
        # Register a TYPE-layer continuous effect so the animation survives
        # EffectManager.apply_all() (which resets card_types to the printed
        # snapshot each recalculation).
        self._register_animation_effect(game)
        self._register_prowess_trigger(game)

    def _register_animation_effect(self, game: Any) -> None:
        """Register a continuous effect re-adding creature type on recalc."""
        effect_manager = getattr(game, "effect_manager", None)
        if effect_manager is None or getattr(self, "_animation_effect_registered", False):
            return
        try:
            from engine.continuous_effects import (
                ContinuousEffect,
                DURATION_PERMANENT,
                Layer,
            )
        except Exception:
            return
        source = self

        def _apply(game: Any) -> None:
            if getattr(source, "_animated", False):
                source.card_types.add(CardType.CREATURE)
                source.subtypes.add("Wizard")

        effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.TYPE,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
        )
        self._animation_effect_registered = True

    # ------------------------------------------------------------------
    # Prowess-style trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        # Only the animated creature carries the prowess trigger; a plain
        # (un-animated) land must not gain any power bonus.
        if CardType.CREATURE in self.card_types:
            self._register_prowess_trigger(game)

    def _register_prowess_trigger(self, game: Any) -> None:
        from engine.triggers import TriggerRegistration

        if getattr(self, "_triggers_registered", False):
            return
        source = self

        def _condition(game: Any, event: Any) -> bool:
            if CardType.CREATURE not in source.card_types:
                return False
            controller = source.controller
            if controller is None:
                return False
            spell = getattr(event, "spell", None)
            if spell is None:
                return False
            if getattr(spell, "controller", None) is not controller:
                return False
            card_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(game: Any) -> None:
            # Model "+1/+0 until end of turn" as a duration-limited MODIFY_PT
            # continuous effect (mirrors cards/fdn/fdn_83).  The engine's
            # end-of-turn cleanup (remove_expired + apply_all) sweeps these,
            # so the buff does not persist into later turns.  Each cast adds
            # one such effect; they stack within a turn and all clear at EOT.
            effect_manager = getattr(game, "effect_manager", None)
            if effect_manager is None:
                # No effect manager (minimal harness): fall back to a direct
                # bump so the within-turn buff is still observable.
                source._power_bonus += 1
                return
            try:
                from engine.continuous_effects import (
                    ContinuousEffect,
                    DURATION_END_OF_TURN,
                    Layer,
                    SubLayer,
                )
            except Exception:
                source._power_bonus += 1
                return

            def _apply(game: Any) -> None:
                source._power_bonus += 1

            effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            # Apply immediately so the buff is observable as soon as the
            # trigger resolves (the engine also recalculates on its own).
            effect_manager.apply_all(game)

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
        self._triggers_registered = True
