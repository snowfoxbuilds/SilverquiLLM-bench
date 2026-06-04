"""Card implementation for Great Hall of the Biblioplex (SOS 257).

Great Hall of the Biblioplex — Land:

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
        an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
        "Whenever you cast an instant or sorcery spell, this creature gets
        +1/+0 until end of turn." It's still a land.

Design notes
------------
* The "Spend this mana only to cast an instant or sorcery spell" rider is
  modelled with the additive restricted-mana surface on ``engine.mana.ManaPool``:
  the any-color ability adds mana via ``add_restricted(..., restriction=
  RESTRICTION_INSTANT_SORCERY)``, and ``engine.casting`` consults the
  restriction when paying so the mana can only pay for instants/sorceries.
* This is a ``Land`` (never a ``Creature`` subclass). Both the animation and
  the per-cast pump are modelled as ``engine.continuous_effects.ContinuousEffect``
  objects added to ``game.effect_manager`` (the established convention — see
  ``cards/fdn/fdn_69`` / ``fdn_71``), NOT as direct attribute mutation:

  - Animation ({5}): a permanent ``Layer.TYPE`` effect that ADDS
    ``CardType.CREATURE`` and the ``"Wizard"`` subtype while keeping
    ``CardType.LAND``, plus a permanent ``Layer.POWER_TOUGHNESS`` ``SET_PT``
    effect setting the land to 2/4. Modelling these as continuous effects is
    REQUIRED because ``EffectManager.apply_all`` calls
    ``_reset_characteristics()`` on every battlefield object on each recalc
    (cleanup / state-based actions); a direct ``card_types`` mutation would be
    stripped on the very next recalc, leaving a permanently non-creature land.
  - Pump ("Whenever you cast an instant or sorcery spell, +1/+0 until end of
    turn"): a per-cast ``Layer.POWER_TOUGHNESS`` ``MODIFY_PT`` effect with
    ``DURATION_END_OF_TURN`` so it expires correctly in the cleanup step (a
    plain attribute accumulator would never decay).

  The land exposes ``power`` / ``toughness`` over ``modified_power`` /
  ``modified_toughness`` (mirroring ``Creature``), which ``_reset_characteristics``
  resets to the land's non-creature baseline of 0/0 before effects reapply.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.mana import RESTRICTION_INSTANT_SORCERY
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_ANY_COLORS = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Colorless land — explicit colors attribute (KEY_DECISIONS convention).
        self.colors: list[str] = []
        # Snapshot the original subtypes so _reset_characteristics can strip the
        # continuous "Wizard" grant the same way the base class strips card_types.
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)
        # Animation state. Until the {5} ability resolves, the land is not a
        # creature and has no power/toughness.
        self._is_animated: bool = False
        # Current P/T, written by continuous effects during apply_all and reset
        # to the land's non-creature baseline (0/0) by _reset_characteristics.
        # Modelled like Creature.modified_power so the layer system owns them.
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        # Guard so register_triggers wires the cast trigger at most once.
        self._cast_trigger_registered: bool = False
        # Guard so the {5} animation registers its continuous effects only once
        # (the becomes-a-creature gate "If this land isn't a creature").
        self._animation_effects_added: bool = False

    # ------------------------------------------------------------------
    # Continuous-effect reset support
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
        """Reset to the non-creature land baseline before effects reapply.

        ``EffectManager.apply_all`` calls this on every recalc; the animation
        (a continuous TYPE + SET_PT effect) then re-adds CREATURE / Wizard / 2/4
        on top, and the per-cast MODIFY_PT effect re-adds the +1/+0 pump if it
        has not yet expired.
        """
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = 0
        self.modified_toughness = 0

    # ------------------------------------------------------------------
    # Power / toughness (only meaningful once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Current power after continuous effects. 0 before animation."""
        return self.modified_power

    @property
    def toughness(self) -> int:
        """Current toughness after continuous effects. 0 before animation."""
        return self.modified_toughness

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

        def _tap_and_pay_life_cost(game: Any, src: Any) -> bool:
            # Atomic: if the tap cannot be paid, do NOT pay life.
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller = src.controller
            if controller is not None:
                controller.life -= 1
            return True

        def _add_colorless(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _add_any_color(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(
                list(_ANY_COLORS),
                "Choose a color of mana to produce",
            )
            # The produced mana may be spent only to cast an instant or sorcery
            # spell — tag it with the restriction so engine.casting enforces it.
            controller.mana_pool.add_restricted(
                chosen, 1, restriction=RESTRICTION_INSTANT_SORCERY
            )

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life_cost,
                mana_produced=_add_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: become a 2/4 Wizard creature (still a land)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _add_type(g: Any) -> None:
            # Layer 4 (type): becomes a creature while staying a land, and
            # gains the Wizard creature subtype.
            source.card_types = set(source.card_types) | {CardType.CREATURE}
            source.subtypes = set(source.subtypes) | {"Wizard"}

        def _set_pt(g: Any) -> None:
            # Layer 7b (set P/T): it's a 2/4 creature.
            source.modified_power = 2
            source.modified_toughness = 4

        def _animate(game: Any) -> None:
            # "If this land isn't a creature" — gate so a second resolution
            # does not register the animation effects (and P/T) twice.
            if source._is_animated or source._animation_effects_added:
                return
            source._is_animated = True
            source._animation_effects_added = True
            # Model the becomes-a-creature change as continuous effects so it
            # survives EffectManager.apply_all's _reset_characteristics pass
            # (a direct card_types mutation would be stripped on the next
            # recalc). The animation lasts as long as the land is in play.
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    apply=_add_type,
                    duration=DURATION_PERMANENT,
                )
            )
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_set_pt,
                    duration=DURATION_PERMANENT,
                )
            )
            # Recalculate immediately so the land reads as a 2/4 creature right
            # away (the engine also recalcs on SBA / cleanup).
            game.effect_manager.apply_all(game)
            # Wire the prowess-like cast trigger now that it is a creature.
            source.register_triggers(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with \"Whenever you cast an instant or "
                    "sorcery spell, this creature gets +1/+0 until end of "
                    "turn.\" It's still a land."
                ),
            )
        ]

    # ------------------------------------------------------------------
    # "Whenever you cast an instant or sorcery spell" pump
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        # Only the animated creature has the cast trigger. Before animation the
        # land has no triggered abilities at all (matches the gate "it becomes
        # a … creature with …").
        if not self._is_animated:
            return
        if self._cast_trigger_registered:
            return
        self._cast_trigger_registered = True

        source = self

        def _controller_casts_instant_or_sorcery(g: GameState, event: Any) -> bool:
            # "Whenever YOU cast" — only the controller's spells count.
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not source.controller:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            card_types = getattr(spell, "card_types", set()) or set()
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _apply_pump(g: Any) -> None:
            # Layer 7c (modify P/T): +1/+0.
            source.modified_power += 1

        def _pump(g: GameState) -> None:
            # "+1/+0 until end of turn" — register a per-cast continuous effect
            # with DURATION_END_OF_TURN so the cleanup step (remove_expired +
            # apply_all) lets it decay. A plain attribute bonus would never
            # reset.
            g.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_pump,
                    duration=DURATION_END_OF_TURN,
                )
            )
            # Recalculate so the pump is visible immediately (engine also
            # recalcs on SBA / cleanup).
            g.effect_manager.apply_all(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_controller_casts_instant_or_sorcery,
                effect=_pump,
                source=self,
                controller=self.controller,
            )
        )
