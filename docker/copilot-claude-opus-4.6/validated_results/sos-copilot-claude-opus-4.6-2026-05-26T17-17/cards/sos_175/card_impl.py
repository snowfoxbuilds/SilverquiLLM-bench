"""Card implementation for Berta, Wise Extrapolator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class BertaWiseExtrapolator(Creature):
    """Berta, Wise Extrapolator — {2}{G}{U} — 1/4 Legendary Creature — Frog Druid.

    Increment (Whenever you cast a spell, if the amount of mana you spent is
    greater than this creature's power or toughness, put a +1/+1 counter on
    this creature.)
    Whenever one or more +1/+1 counters are put on Berta, add one mana of any color.
    {X}, {T}: Create a 0/0 green and blue Fractal creature token and put X
    +1/+1 counters on it.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Berta, Wise Extrapolator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        kwargs.setdefault("subtypes", {"Frog", "Druid"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register increment and counter-mana triggers."""
        from engine.events import SpellCastTriggeredEvent, CounterAddedTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = self.controller

        # Increment trigger
        def _increment_condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            if event.player is not source.controller:
                return False
            mana_spent = getattr(event, "mana_spent", 0)
            if mana_spent is None:
                mana_spent = 0
            # Greater than power OR toughness
            return mana_spent > source.power or mana_spent > source.toughness

        def _increment_effect(game: "GameState") -> None:
            source.plus_one_counters += 1
            source._base_plus_one_counters = source.plus_one_counters

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_increment_condition,
            effect=_increment_effect,
            source=self,
            controller=controller,
        ))

        # Counter-mana trigger (whenever +1/+1 counters put on Berta)
        def _counter_condition(game: "GameState", event: CounterAddedTriggeredEvent) -> bool:
            return event.permanent is source and event.counter_type == "+1/+1"

        def _counter_effect(game: "GameState") -> None:
            # Add one mana of any color (engine limitation: add green by default)
            ctrl = source.controller
            if ctrl is not None and hasattr(ctrl, "mana_pool"):
                from engine.types import ManaType
                ctrl.mana_pool.add(ManaType.GREEN, 1)

        game.trigger_manager.register(TriggerRegistration(
            event_type=CounterAddedTriggeredEvent,
            condition=_counter_condition,
            effect=_counter_effect,
            source=self,
            controller=controller,
        ))

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """{X}, {T}: Create a 0/0 G/U Fractal token with X +1/+1 counters."""
        source = self

        def _cost(game: "GameState", card: Any = None) -> bool:
            return not source.is_tapped

        def _effect(game: "GameState", card: Any = None, x: int = 0, **kwargs: Any) -> None:
            src = card if card is not None else source
            ctrl = src.controller
            if ctrl is None:
                return
            src.is_tapped = True

            # Create a 0/0 green and blue Fractal creature token
            token = Creature(
                name="Fractal",
                owner=ctrl,
                controller=ctrl,
                base_power=0,
                base_toughness=0,
                card_types={CardType.CREATURE},
                subtypes={"Fractal"},
            )
            token.is_token = True
            token.plus_one_counters = x
            token._base_plus_one_counters = x
            game.get_battlefield(ctrl).add(token)

        ability = ActivatedAbility(cost=_cost, effect=_effect,
                                   description="{X}, {T}: Create a 0/0 G/U Fractal with X +1/+1 counters.")
        ability.tap_cost = True
        return [ability]
