"""Card implementation for Cathar Commando."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_artifact_or_enchantment(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.ARTIFACT in types or CardType.ENCHANTMENT in types


class CatharCommando(Creature):
    """Cathar Commando — {1}{W} — 3/1 — Human Soldier

    Flash
    {1}, Sacrifice this creature: Destroy target artifact or enchantment.

    FDN collector number 139.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cathar Commando")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Soldier"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\n{1}, Sacrifice this creature: Destroy target artifact "
            "or enchantment.",
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
            # Choose the target at activation (rule 602.2b), before the cost
            # sacrifices this creature.
            candidates = [
                obj
                for player in game.players
                for obj in game.get_battlefield(player).get_all()
                if _is_artifact_or_enchantment(obj)
            ]
            if not candidates:
                return None
            target = choose_object(
                game,
                controller,
                candidates,
                "Choose target artifact or enchantment to destroy",
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
            if controller.mana_pool.total() < 1:
                return False
            controller.mana_pool.pay(ManaCost(generic=1))
            sacrifice(game, controller, src)
            return True

        def _effect(
            game: "GameState", targets: list[Any], context: Any = None
        ) -> None:
            from engine.game import destroy

            target = targets[0] if targets else None
            if target is None or not _on_battlefield(game, target):
                return
            # Revalidate the target is still an artifact or enchantment.
            if not _is_artifact_or_enchantment(target):
                return
            destroy(game, target)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                targeting=_targeting,
                can_activate=_can_activate,
                description="{1}, Sacrifice this creature: Destroy target "
                "artifact or enchantment.",
            )
        ]
