from types import SimpleNamespace

from engine.card import Sorcery
from engine.casting import grant_cast_permission
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone

# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class InsideInformationAbility1:
    text = "Exile the top X cards of target opponent's library. You may play those cards this turn. If you cast a spell this way, pay life equal to its mana value rather than pay its mana cost."


# endregion Printed abilities


class InsideInformation(Sorcery):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Inside Information',
            'mana_cost': ManaCost.parse('{X}{B}{B}'),
            'rules_text': "Exile the top X cards of target opponent's library. You may play those cards this turn. If you cast a spell this way, pay life equal to its mana value rather than pay its mana cost.",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def get_targets(self, game):
        return [SimpleNamespace(zone=None, description='target opponent',
                filter_fn=lambda obj: obj in game.players and obj is not self.controller)]

    def on_resolve(self, game):
        targets = getattr(self, 'chosen_targets', [])
        if not targets or targets[0] not in game.players or targets[0] is self.controller:
            return
        for card in targets[0].zones[Zone.LIBRARY].top(self.x_value):
            move_to_zone(game, card, Zone.LIBRARY, Zone.EXILE)
            grant_cast_permission(game, self.controller, card,
                                  until_turn=game.turn_number, life_cost=True)
