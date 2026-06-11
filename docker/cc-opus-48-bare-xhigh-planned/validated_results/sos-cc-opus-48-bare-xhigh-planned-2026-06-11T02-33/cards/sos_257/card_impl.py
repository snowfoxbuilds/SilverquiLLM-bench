"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLORS = (ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN)
_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
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
        # +1/+0-until-EOT accumulator; meaningful only while animated.
        self._pump_power: int = 0

    # ------------------------------------------------------------------
    # Animated P/T (only while this land is also a creature)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if CardType.CREATURE not in self.card_types:
            return 0
        return getattr(self, "_anim_power", 0) + self._pump_power

    @property
    def toughness(self) -> int:
        if CardType.CREATURE not in self.card_types:
            return 0
        return getattr(self, "_anim_toughness", 0)

    def _reset_characteristics(self) -> None:
        """Reset until-end-of-turn modifiers (the pump) without de-animating.

        Called by ``EffectManager.apply_all`` (during the cleanup step).
        Deliberately does NOT call ``super()._reset_characteristics()`` —
        that would revert ``card_types`` to the un-animated land, but the
        animation is permanent ("It's still a land", not "until end of turn").
        Only the +1/+0 pump is an until-EOT effect, so only it resets here.
        """
        self.keywords = self._original_keywords
        self._pump_power = 0

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
            if source.controller is not None:
                source.controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: "GameState", src: Any) -> bool:
            ctrl = source.controller
            if getattr(src, "is_tapped", False):
                return False
            if ctrl is None or getattr(ctrl, "life", 0) < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_restricted(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            color = ctrl.choose(list(_COLORS), "choose a color of mana to add")
            if color not in _COLORS:
                color = _COLORS[0]
            # Restricted: spend only to cast an instant or sorcery spell.
            ctrl.mana_pool.add(color, 1, restricted=True)

        return [
            ManaAbility(cost=_tap, mana_produced=_add_colorless,
                        description="{T}: Add {C}."),
            ManaAbility(cost=_tap_pay_life, mana_produced=_add_any_restricted,
                        description="{T}, Pay 1 life: Add one mana of any color "
                        "(spend only on an instant or sorcery)."),
        ]

    # ------------------------------------------------------------------
    # {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: "GameState", src: Any) -> bool:
            ctrl = source.controller
            if ctrl is None:
                return False
            cost = ManaCost(generic=5)
            # Ability costs are not "casting a spell" → restricted mana cannot pay.
            if not ctrl.mana_pool.can_pay(cost, allow_restricted=False):
                return False
            return ctrl.mana_pool.pay(cost, allow_restricted=False)

        def _animate(game: "GameState") -> None:
            source._become_creature(game)

        return [ActivatedAbility(
            cost=_pay_five, effect=_animate,
            description="{5}: Become a 2/4 Wizard if not already a creature (still a land).",
        )]

    def _become_creature(self, game: "GameState") -> None:
        """Mutate in place into a 2/4 Wizard creature (only if not already one)."""
        if CardType.CREATURE in self.card_types:
            return
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self._anim_power = 2
        self._anim_toughness = 4
        # base_power/base_toughness presence makes it a legal combatant.
        self.base_power = 2
        self.base_toughness = 4
        self._pump_power = 0
        self.damage_marked = getattr(self, "damage_marked", 0)
        self.summoning_sick = False  # has been on the battlefield
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._register_pump(game)

    def _register_pump(self, game: "GameState") -> None:
        """Whenever you cast an instant/sorcery, this gets +1/+0 until EOT."""
        from engine.triggers import TriggerRegistration
        from engine.events import SpellCastTriggeredEvent

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _cond(g: Any, ev: Any) -> bool:
            if CardType.CREATURE not in source.card_types:
                return False
            caster = getattr(ev, "controller", None) or getattr(ev, "player", None)
            if caster is not source.controller:
                return False
            spell_obj = getattr(ev, "spell", None)
            spell_card = getattr(spell_obj, "source", None) if spell_obj else None
            spell_card = spell_card or getattr(ev, "card", None)
            return bool(getattr(spell_card, "card_types", set()) & _SPELL_TYPES)

        def _eff(g: "GameState") -> None:
            source._pump_power += 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_cond,
            effect=_eff,
            source=self,
            controller=controller,
        ))
