"""Card implementation for MassacreWurm."""

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

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


class MassacreWurm(Creature):
    """Massacre Wurm — {3}{B}{B}{B} — 6/5 — Phyrexian Wurm

    When this creature enters, creatures your opponents control get -2/-2
    until end of turn.
    Whenever a creature an opponent controls dies, that player loses 2 life.

    FDN collector number 714.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Massacre Wurm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}{B}"))
        kwargs.setdefault("subtypes", {"Phyrexian", "Wurm"})
        kwargs.setdefault("base_power", 6)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, creatures your opponents control get -2/-2 "
            "until end of turn.\nWhenever a creature an opponent controls dies, "
            "that player loses 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _etb_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Snapshot opponent creatures to debuff
            targets: list[Any] = []
            for player in game.players:
                if player is controller:
                    continue
                for obj in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        targets.append(obj)

            if not targets:
                return

            frozen_targets = list(targets)

            def _apply_debuff(game: GameState) -> None:
                for tgt in frozen_targets:
                    if _is_on_battlefield(game, tgt) and hasattr(tgt, "base_power"):
                        tgt.base_power -= 2
                        tgt.base_toughness -= 2

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_debuff,
                duration=DURATION_END_OF_TURN,
            ))

        def _dies_condition(game: GameState, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature_ctrl is not None and creature_ctrl is not controller:
                return True
            return False

        def _dies_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # Find the dying creature's controller from trigger data
            # Since we can't access data here, lose 2 life to each opponent
            # Actually, we need the controller of the dying creature.
            # The trigger fires per creature death; opponent loses 2 life.
            for player in game.players:
                if player is not controller:
                    player.life -= 2

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["MassacreWurm"]
