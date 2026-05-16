"""Card implementation for Goblin Bushwhacker."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Artifact, Creature, Enchantment, Instant, ManaAbility, Sorcery
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, DURATION_PERMANENT, Layer, SubLayer
from engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: dict) -> bool:
        return event.permanent is source
    return _condition

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class GoblinBushwhacker(Creature):
    """Goblin Bushwhacker — {R} — 1/1 — Goblin Warrior

    Kicker {R}.
    When this creature enters the battlefield, if it was kicked,
    creatures you control get +1/+0 and gain haste until end of turn.

    SPG collector number 78.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Goblin Bushwhacker')
        kwargs.setdefault('mana_cost', ManaCost.parse('{R}'))
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('subtypes', {'Goblin', 'Warrior'})
        kwargs.setdefault('rules_text', 'Kicker {R}\nWhen Goblin Bushwhacker enters the battlefield, if it was kicked, creatures you control get +1/+0 and gain haste until end of turn.')
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse('{R}')
        self.has_kicker: bool = True

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        source = self

        def _etb_effect(g: GameState) -> None:
            if not source.kicked:
                return
            controller = source.controller or source.owner
            if controller is None:
                return
            bf = g.get_battlefield(controller)
            creatures = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, 'card_types', set())]
            affected = list(creatures)

            def _apply(game_state: Any) -> None:
                for creature in affected:
                    if _is_on_battlefield(game_state, creature):
                        creature.base_power += 1
                        creature.keywords = creature.keywords | Keyword.HASTE

            def _remove(game_state: Any) -> None:
                for creature in affected:
                    if _is_on_battlefield(game_state, creature):
                        creature.base_power -= 1
                        creature.keywords = Keyword(creature.keywords & ~Keyword.HASTE)
            g.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply, duration=DURATION_END_OF_TURN))
        reg = TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_etb_effect, source=self, controller=self.controller or self.owner)
        game.trigger_manager.register(reg)
