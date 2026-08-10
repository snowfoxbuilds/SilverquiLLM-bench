"""Card implementation for Axgard Cavalry."""

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
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _can_tap(source: Any) -> bool:
    """Return ``True`` if *source* can pay a ``{T}`` cost (rule 302.6)."""
    if getattr(source, "is_tapped", False):
        return False
    keywords = getattr(source, "keywords", Keyword(0))
    if getattr(source, "summoning_sick", False) and Keyword.HASTE not in keywords:
        return False
    return True


class AxgardCavalry(Creature):
    """Axgard Cavalry — {1}{R} — 2/2 — Dwarf Berserker

    {T}: Target creature gains haste until end of turn.

    FDN collector number 189.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Axgard Cavalry")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Berserker"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{T}: Target creature gains haste until end of turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # The source must be on the battlefield and able to pay the tap cost.
            return (
                controller is not None
                and _on_battlefield(game, src)
                and _can_tap(src)
            )

        def _targeting(
            game: "GameState", src: Any, controller: Any
        ) -> list[Any] | None:
            # Any creature on the battlefield is a legal target.
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
                "Choose target creature to gain haste",
                source_card=src,
            )
            if target is None:
                return None
            return [target]

        def _cost(game: "GameState", src: Any) -> bool:
            if not _can_tap(src):
                return False
            src.is_tapped = True
            return True

        def _effect(
            game: "GameState", targets: list[Any], context: Any = None
        ) -> None:
            # Revalidate via the shared helper: same battlefield stint and still
            # a creature.
            legal = surviving_targets(
                game, context, targets,
                is_legal=lambda t: CardType.CREATURE in getattr(t, "card_types", set()),
            )
            chosen = legal[0] if legal else None
            if chosen is None:
                return

            def _apply(g: "GameState") -> None:
                chosen.keywords = getattr(chosen, "keywords", Keyword(0)) | Keyword.HASTE

            # Until-end-of-turn: keywords are reset to their originals on every
            # apply_all() pass, so the grant is re-applied by this effect.
            chosen.keywords = chosen.keywords | Keyword.HASTE
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
                description="{T}: Target creature gains haste until end of turn.",
            )
        ]
