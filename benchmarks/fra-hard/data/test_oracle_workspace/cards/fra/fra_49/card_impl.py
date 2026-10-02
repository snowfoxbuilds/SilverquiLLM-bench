from engine.card import Creature, Instant
from engine.events import EndStepTriggeredEvent
from engine.game import draw_card, lose_life
from engine.preparation import consume_preparation, prepare
from engine.triggers import TriggerRegistration
from engine.types import ManaCost, TargetRequirement, Zone
from engine.zones import creatures_died_this_turn


class AncestralCraving(Instant):
    def __init__(self, **kwargs):
        super().__init__(name="Ancestral Craving", mana_cost=ManaCost.parse("{B}"), **kwargs)

    def get_targets(self, game):
        return [TargetRequirement(lambda obj: obj in game.players, "Target player", Zone.BATTLEFIELD)]

    def on_cast(self, game):
        consume_preparation(game, self)

    def on_resolve(self, game):
        for player in self.chosen_targets:
            for _ in range(3):
                draw_card(game, player)
            lose_life(game, player, 3, source=self)


class BloodlineRecollector(Creature):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Bloodline Recollector',
            'mana_cost': ManaCost.parse('{1}{B}'),
            'rules_text': "At the beginning of each end step, if three or more creatures died this turn, this creature becomes prepared. (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)",
            'base_power': 2,
            'base_toughness': 2,
            'subtypes': {'Vampire', 'Warlock'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def register_triggers(self, game):
        stint = game.refs.zone_epoch(self)

        def effect(state):
            if game.refs.zone_epoch(self) == stint and creatures_died_this_turn(state) >= 3:
                prepare(state, self, AncestralCraving)

        game.trigger_manager.register(TriggerRegistration(
            EndStepTriggeredEvent,
            lambda state, event: creatures_died_this_turn(state) >= 3,
            effect, self, self.controller,
        ))
