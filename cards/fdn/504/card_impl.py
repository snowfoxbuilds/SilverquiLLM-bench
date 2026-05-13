"""Card implementation for BurrogBefuddler."""

from __future__ import annotations


from engine.card import ArtifactCreature, Creature
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition

def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


class BurrogBefuddler(Creature):
    """Burrog Befuddler — {1}{U} — 2/1 — Frog Wizard — Flash

    When this creature enters, target creature an opponent controls gets
    -1/-0 until end of turn.

    FDN collector number 504.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burrog Befuddler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Frog", "Wizard"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\nWhen this creature enters, target creature an opponent controls "
            "gets -1/-0 until end of turn.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _effect(game: GameState) -> None:
            target = _get_chosen_target(source, game)
            if target is None or not _is_on_battlefield(game, target):
                return
            if not hasattr(target, "base_power"):
                return

            tgt = target

            def _apply_debuff(game: GameState) -> None:
                if _is_on_battlefield(game, tgt) and hasattr(tgt, "base_power"):
                    tgt.base_power -= 1

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_debuff,
                duration=DURATION_END_OF_TURN,
            ))

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["BurrogBefuddler"]
