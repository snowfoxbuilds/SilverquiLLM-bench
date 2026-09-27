"""Card implementation for Heartfire Immolator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.stack import surviving_targets
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _creature_or_planeswalker(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.CREATURE in types or CardType.PLANESWALKER in types


class HeartfireImmolator(Creature):
    """Heartfire Immolator — {1}{R} — 2/2 — Human Wizard

    Prowess
    {R}, Sacrifice this creature: It deals damage equal to its power to
    target creature or planeswalker.

    FDN collector number 201.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heartfire Immolator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("keywords", Keyword.PROWESS)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Prowess\n{R}, Sacrifice this creature: It deals damage equal "
            "to its power to target creature or planeswalker.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # Instant-speed ability: the only legality gate is that the source
            # is still on the battlefield to be sacrificed.
            return controller is not None and _on_battlefield(game, src)

        def _targeting(
            game: "GameState", src: Any, controller: Any
        ) -> list[Any] | None:
            candidates = [
                obj
                for player in game.players
                for obj in game.get_battlefield(player).get_all()
                if _creature_or_planeswalker(obj)
            ]
            if not candidates:
                return None
            target = choose_object(
                game,
                controller,
                candidates,
                "Choose target creature or planeswalker",
                source_card=src,
            )
            if target is None:
                return None
            return [target]

        def _cost(game: "GameState", src: Any) -> bool:
            from engine.game import sacrifice

            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{R}"))
            # Snapshot power as last-known information before the sacrifice —
            # the damage is dealt after the source has left the battlefield.
            src._snapshot_power = getattr(src, "modified_power", src.base_power)
            sacrifice(game, controller, src)
            return True

        def _effect(
            game: "GameState", targets: list[Any], context: Any = None
        ) -> None:
            from engine.game import deal_damage

            # Revalidate via the shared helper: same battlefield stint and still
            # a creature or planeswalker.
            legal = surviving_targets(
                game, context, targets, is_legal=_creature_or_planeswalker
            )
            target = legal[0] if legal else None
            if target is None:
                return
            dmg = getattr(source, "_snapshot_power", source.base_power)
            deal_damage(game, source, target, dmg)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                targeting=_targeting,
                can_activate=_can_activate,
                description="{R}, Sacrifice this creature: It deals damage "
                "equal to its power to target creature or planeswalker.",
            )
        ]
