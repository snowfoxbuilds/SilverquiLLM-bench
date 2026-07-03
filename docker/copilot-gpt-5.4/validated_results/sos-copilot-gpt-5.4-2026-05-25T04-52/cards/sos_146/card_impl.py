"""Card implementation for Emil, Vastlands Roamer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
)
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class EmilVastlandsRoamer(Creature):
    """Emil, Vastlands Roamer."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emil, Vastlands Roamer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.colors = {Color.GREEN}

    def apply_continuous_effect(self, game: GameState) -> list[ContinuousEffect]:
        source = self

        def _apply(g: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None or not source.is_on_battlefield(g):
                return
            for permanent in g.get_battlefield(controller).get_all():
                if isinstance(permanent, Creature) and permanent.plus_one_counters > 0:
                    permanent.keywords |= Keyword.TRAMPLE

        existing = game.effect_manager.get_effects_by_source(self)
        if existing:
            return existing
        effect = game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
        )
        return [effect]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, card: EmilVastlandsRoamer) -> bool:
            controller = card.controller
            if controller is None or card.is_tapped:
                return False
            if (
                getattr(card, "summoning_sick", False)
                and Keyword.HASTE not in getattr(card, "keywords", Keyword(0))
                and not game.is_fresh_setup_sandbox(controller)
            ):
                return False
            mana_cost = ManaCost.parse("{4}{G}")
            if not controller.mana_pool.can_pay(mana_cost):
                return False
            controller.mana_pool.pay(mana_cost)
            card.is_tapped = True
            return True

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            differently_named_lands = {
                permanent.name
                for permanent in game.get_battlefield(controller).get_all()
                if CardType.LAND in getattr(permanent, "card_types", set())
            }
            token = Creature(
                name="Fractal",
                owner=controller,
                controller=controller,
                subtypes={"Fractal"},
                base_power=0,
                base_toughness=0,
            )
            token.colors = {Color.GREEN, Color.BLUE}
            token.plus_one_counters = len(differently_named_lands)
            token._base_plus_one_counters = token.plus_one_counters
            create_token(game, controller, token)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{4}{G}, {T}: Create a Fractal token.",
            )
        ]
