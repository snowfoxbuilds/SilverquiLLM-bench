"""Card implementation for Great Hall of the Biblioplex (SOS 257).

Great Hall of the Biblioplex is a colorless Land with three abilities:

  {T}: Add {C}.
  {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
      an instant or sorcery spell.
  {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
      "Whenever you cast an instant or sorcery spell, this creature gets
      +1/+0 until end of turn." It's still a land.

Animation is modelled with the continuous-effect layer system:
  * Layer 4 (TYPE): add CREATURE to ``card_types`` (LAND is retained) and add
    the "Wizard" subtype.
  * Layer 7b (SET_PT): set ``modified_power``/``modified_toughness`` to 2/4.

The granted "Whenever you cast an instant or sorcery spell, this creature gets
+1/+0 until end of turn" trigger is registered through the spell-cast trigger
machinery (``SpellCastTriggeredEvent``, now fired by ``engine.casting.cast_spell``).
It is controller-scoped and only fires while the permanent is actually a
creature (CREATURE in ``card_types``); each qualifying instant/sorcery the
controller casts registers a Layer 7c +1/+0 ``DURATION_END_OF_TURN`` continuous
effect, so the animated creature's POWER increases by 1 per cast and resets at
end of turn (the cleanup step sweeps the until-end-of-turn effects).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


# The five colors a player may produce with the any-color ability.
_COLOR_OPTIONS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


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
        # Creature characteristics granted only while animated.  Lands have no
        # P/T by default; these mirror the Creature surface so the test (and
        # combat) can read ``card.power`` / ``card.toughness`` once animated.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.summoning_sick: bool = True
        # Snapshot the printed (non-creature) subtypes for reset.
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)
        # Reference to the permanent animation effects so re-activation is a
        # no-op (the "If this land isn't a creature" guard).
        self._animation_effects: list[Any] = []
        self._cast_trigger_registered: bool = False

    # ------------------------------------------------------------------
    # Power / toughness surface (only meaningful while animated)
    # ------------------------------------------------------------------
    @property
    def power(self) -> int:
        """Current power (0 unless animated; continuous effects set it)."""
        return self.modified_power

    @property
    def toughness(self) -> int:
        """Current toughness (0 unless animated; continuous effects set it)."""
        return self.modified_toughness

    def _reset_characteristics(self) -> None:
        """Reset to printed (non-creature) characteristics before reapply.

        ``Land._reset_characteristics`` only resets ``card_types`` and
        ``keywords``; the animation also touches ``subtypes`` and P/T, so we
        reset those here so ``EffectManager.apply_all`` stays idempotent.
        """
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

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

        def _tap_pay_life_cost(game: Any, src: Any) -> bool:
            # A tapped source cannot pay the tap cost; do NOT drain life on a
            # failed activation.
            if getattr(src, "is_tapped", False):
                return False
            controller = src.controller
            if controller is None:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_effect(game: Any) -> None:
            # UNVERIFIED: "spend this mana only to cast an instant or sorcery spell" — engine has no mana spend-restriction surface (matches FDN 267 Secluded Courtyard limitation).
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(
                list(_COLOR_OPTIONS),
                "Choose a color of mana to produce",
            )
            controller.mana_pool.add(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_any_color_effect,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation activated ability
    # ------------------------------------------------------------------
    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _effect(game: Any) -> None:
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature. It's still a land."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def _animate(self, game: GameState) -> None:
        """Become a 2/4 Wizard creature (still a land), guarding re-animation.

        "If this land isn't a creature, it becomes ..." — if it is already a
        creature (animation effects already registered), this is a no-op so the
        P/T does not stack.
        """
        if CardType.CREATURE in self.card_types or self._animation_effects:
            return

        card = self

        def _apply_type(game: GameState) -> None:
            if not _is_on_battlefield(game, card):
                return
            card.card_types = set(card.card_types) | {CardType.CREATURE}
            card.subtypes = set(card.subtypes) | {"Wizard"}

        def _apply_pt(game: GameState) -> None:
            if not _is_on_battlefield(game, card):
                return
            if CardType.CREATURE not in card.card_types:
                return
            card.modified_power = 2
            card.modified_toughness = 4

        type_effect = ContinuousEffect(
            source=self,
            layer=Layer.TYPE,
            sublayer=None,
            apply=_apply_type,
            duration=DURATION_PERMANENT,
        )
        pt_effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.SET_PT,
            apply=_apply_pt,
            duration=DURATION_PERMANENT,
        )
        self._animation_effects = [
            game.effect_manager.add(type_effect),
            game.effect_manager.add(pt_effect),
        ]
        # Apply immediately so the type is live before any further queries.
        game.effect_manager.apply_all(game)
        # Ensure the granted cast trigger is registered (once).
        self._register_cast_trigger(game)

    # ------------------------------------------------------------------
    # Granted "whenever you cast an instant or sorcery spell" trigger
    # ------------------------------------------------------------------
    def register_triggers(self, game: GameState) -> None:
        # Register up-front so animation that happens after the permanent is
        # already tracked still benefits; the condition gates on being a
        # creature, so it is inert until animated.
        self._register_cast_trigger(game)

    def _register_cast_trigger(self, game: GameState) -> None:
        if self._cast_trigger_registered:
            return
        trigger_manager = getattr(game, "trigger_manager", None)
        if trigger_manager is None:
            return
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            # Only while animated (a creature) and on the battlefield.
            if CardType.CREATURE not in source.card_types:
                return False
            if not _is_on_battlefield(game, source):
                return False
            controller = source.controller
            if controller is None:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            # Only the controller's own instant/sorcery spells.
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            spell_controller = getattr(spell, "controller", None)
            if caster is not controller and spell_controller is not controller:
                return False
            card_types = getattr(spell, "card_types", set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: GameState) -> None:
            source._pump_until_end_of_turn(game)

        controller = getattr(self, "controller", None) or game.active_player
        trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
        self._cast_trigger_registered = True

    def _pump_until_end_of_turn(self, game: GameState) -> None:
        """Give this creature +1/+0 until end of turn (per qualifying cast)."""
        card = self

        def _apply_pump(game: GameState) -> None:
            if not _is_on_battlefield(game, card):
                return
            if CardType.CREATURE not in card.card_types:
                return
            card.modified_power += 1

        pump = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_pump,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(pump)
        game.effect_manager.apply_all(game)
