"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_ANIMATE_COST = "{5}"
_ANIMATED_POWER = 2
_ANIMATED_TOUGHNESS = 4

_ANY_COLOR = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
        an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
        "Whenever you cast an instant or sorcery spell, this creature gets
        +1/+0 until end of turn." It's still a land.

    While un-animated this is *not* a creature and deliberately does not
    expose ``power``/``toughness`` (the ``toughness`` attribute being absent
    keeps the zero-toughness state-based action from destroying it).
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
        self._animated = False
        self._cur_power = 0
        self._cur_toughness = 0
        self._power_bonus = 0
        self.damage_marked = 0

    # ------------------------------------------------------------------
    # Power / toughness — only exposed once animated
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if not self._animated:
            raise AttributeError("power")
        return self._cur_power + self._power_bonus

    @property
    def toughness(self) -> int:
        if not self._animated:
            raise AttributeError("toughness")
        return self._cur_toughness

    def _reset_characteristics(self) -> None:
        # Base reset restores card_types to {LAND} and clears keyword grants.
        super()._reset_characteristics()
        # The +1/+0 buffs last only until end of turn.
        self._power_bonus = 0
        # The animation itself is permanent, so re-establish it after the
        # base reset wiped CREATURE from card_types.
        if self._animated:
            self.card_types = self.card_types | {CardType.CREATURE}
            self._cur_power = _ANIMATED_POWER
            self._cur_toughness = _ANIMATED_TOUGHNESS

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def _animate(self, game: "GameState") -> None:
        # "If this land isn't a creature, it becomes ..."
        if CardType.CREATURE in self.card_types:
            return
        self._animated = True
        self.card_types = self.card_types | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self._cur_power = _ANIMATED_POWER
        self._cur_toughness = _ANIMATED_TOUGHNESS
        self._power_bonus = 0
        self.damage_marked = 0
        # It has been on the battlefield as a land, so it isn't summoning sick.
        self.summoning_sick = False

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
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_and_pay_life(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if getattr(src, "is_tapped", False):
                return False
            if controller is None or controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_any_color(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            color = controller.choose(list(_ANY_COLOR), "choose a color of mana")
            if color not in _ANY_COLOR:
                color = ManaType.WHITE
            controller.mana_pool.add(color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self, game: "GameState") -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost.parse(_ANIMATE_COST))

        def _effect(game: "GameState") -> None:
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

    # ------------------------------------------------------------------
    # Triggered ability gained while animated
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            # The ability exists only while this land is a creature.
            if CardType.CREATURE not in source.card_types:
                return False
            controller = source.controller
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if controller is None or caster is not controller:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            return _is_instant_or_sorcery(spell)

        def _effect(g: "GameState") -> None:
            source._power_bonus += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller or self.owner,
            )
        )
