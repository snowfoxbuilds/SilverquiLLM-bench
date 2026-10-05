from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.planeswalker import empower_jace
from engine.triggers import TriggerRegistration
from engine.types import ManaCost


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SanctumLurkerAbility1:
    text = 'When this creature enters, empower Jace 1.'


class SanctumLurkerAbility2:
    text = "Planeswalkers you control aren't put into their owners' graveyards for having 0 loyalty."


class SanctumLurkerAbility3:
    text = 'Planeswalkers you control have "[+2]: This planeswalker deals 1 damage to each opponent and you gain 1 life."'


# endregion Printed abilities


class SanctumLurker(Creature):
    protects_zero_loyalty = True
    grants_drain_loyalty = True
    drain_loyalty_printed = SanctumLurkerAbility3

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Sanctum Lurker',
            'mana_cost': ManaCost.parse('{2}{B}'),
            'rules_text': 'When this creature enters, empower Jace 1.\nPlaneswalkers you control aren\'t put into their owners\' graveyards for having 0 loyalty.\nPlaneswalkers you control have "[+2]: This planeswalker deals 1 damage to each opponent and you gain 1 life."',
            'base_power': 3,
            'base_toughness': 2,
            'subtypes': {'Horror'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def register_triggers(self, game):
        game.trigger_manager.register(TriggerRegistration(
            EntersBattlefieldTriggeredEvent,
            lambda state, event: event.permanent is self,
            lambda state, controller: empower_jace(state, controller, 1, self),
            self, self.controller, printed=SanctumLurkerAbility1,
        ))
