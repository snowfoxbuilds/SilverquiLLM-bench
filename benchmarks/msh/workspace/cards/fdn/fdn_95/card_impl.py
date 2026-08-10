"""Card implementation for Sower of Chaos."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.stack import surviving_targets
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    ContinuousEffect,
    Layer,
)
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class SowerOfChaos(Creature):
    """Sower of Chaos — {3}{R} — 4/3 — Devil

    {2}{R}: Target creature can't block this turn.

    FDN collector number 95.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sower of Chaos")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("subtypes", {"Devil"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "{2}{R}: Target creature can't block this turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # Legality (rule 602.2a): the source must be on the battlefield.
            # The ability is instant speed, so there is no timing gate.
            return controller is not None and _on_battlefield(game, src)

        def _cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            if controller.mana_pool.total() < 3:
                return False
            controller.mana_pool.pay(ManaCost.parse("{2}{R}"))
            return True

        def _targeting(
            game: "GameState", src: Any, controller: Any
        ) -> list[Any] | None:
            # Choose the target creature at activation (rule 602.2b), before the
            # cost is paid. Any creature on the battlefield is a legal target.
            creatures = [
                obj
                for player in game.players
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ]
            if not creatures:
                return None
            target = choose_object(
                game,
                controller,
                creatures,
                "Choose target creature that can't block this turn",
                source_card=src,
            )
            if target is None:
                return None
            return [target]

        def _effect(
            game: "GameState", targets: list[Any], context: Any = None
        ) -> None:
            # Resolve using the target chosen at activation; never re-select.
            # Revalidate via the shared helper: same battlefield stint (a
            # leave-and-return is a new object) and still a creature.
            legal = surviving_targets(
                game, context, targets,
                is_legal=lambda t: CardType.CREATURE in getattr(t, "card_types", set()),
            )
            chosen = legal[0] if legal else None
            if chosen is None:
                return

            def _apply(g: "GameState") -> None:
                chosen._cant_block = True

            # Until-end-of-turn: _cant_block is reset on every apply_all() pass,
            # so a bare assignment would not survive re-derivation.
            chosen._cant_block = True
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.ABILITY,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                targeting=_targeting,
                can_activate=_can_activate,
                description="{2}{R}: Target creature can't block this turn.",
            )
        ]
