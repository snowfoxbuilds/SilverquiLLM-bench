"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState

_SPELL_TYPES = {CardType.INSTANT, CardType.SORCERY}

_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
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
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard '
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._animated: bool = False

    # ------------------------------------------------------------------
    # P/T (meaningful only while animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return (
            getattr(self, "modified_power", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    @property
    def toughness(self) -> int:
        return (
            getattr(self, "modified_toughness", 0)
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    def _reset_characteristics(self) -> None:
        """Keep the animated state across continuous-effect recalculation."""
        super()._reset_characteristics()
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life_cost(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None or controller.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            try:
                chosen = controller.choose(list(_COLORS), "Choose a color of mana to add")
            except Exception:
                chosen = _COLORS[0]
            if chosen not in _COLORS:
                chosen = _COLORS[0]
            controller.mana_pool.add(chosen, 1, restriction="instant_sorcery")

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_add_restricted_any_color,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation (activated ability)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: GameState, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _animate(game: GameState) -> None:
            source._do_animate(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description="{5}: If this land isn't a creature, it becomes "
                "a 2/4 Wizard creature with \"Whenever you cast an instant "
                "or sorcery spell, this creature gets +1/+0 until end of "
                "turn.\" It's still a land.",
            )
        ]

    def _do_animate(self, game: GameState) -> None:
        """Become a 2/4 Wizard creature (still a land), in place."""
        if CardType.CREATURE in self.card_types:
            return  # already a creature — the ability does nothing

        self._animated = True
        self.card_types.add(CardType.CREATURE)
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
        # Deliberate simplification (per plan): the land has been on the
        # battlefield, so the animated creature is not summoning sick.
        self.summoning_sick = False

        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            if not source._animated:
                return False
            ctrl = getattr(source, "controller", None)
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            spell_card = getattr(event, "card", None)
            return bool(_SPELL_TYPES & getattr(spell_card, "card_types", set()))

        def _pump(g: GameState) -> None:
            # +1/+0 until end of turn — direct modification, swept when the
            # cleanup step resets characteristics (FDN prowess style).
            if source._animated:
                source.modified_power += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_pump,
                source=self,
                controller=self.controller,
            )
        )

    def register_triggers(self, game: GameState) -> None:
        """Watch for this card leaving the battlefield to drop animation."""
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _leave_condition(g: Any, event: Any) -> bool:
            # De-animate synchronously (a fresh card object is not a
            # creature); never push anything onto the stack.
            if getattr(event, "permanent", None) is source and source._animated:
                source._animated = False
                source.card_types.discard(CardType.CREATURE)
                source.subtypes.discard("Wizard")
                for attr in ("base_power", "base_toughness", "modified_power",
                             "modified_toughness", "damage_marked"):
                    if hasattr(source, attr):
                        delattr(source, attr)
            return False

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_leave_condition,
                effect=lambda g: None,
                source=self,
                controller=getattr(self, "controller", None) or game.active_player,
            )
        )
