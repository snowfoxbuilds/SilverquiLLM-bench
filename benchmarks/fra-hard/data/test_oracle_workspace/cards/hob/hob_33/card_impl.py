from engine.card import Creature
from engine.card_queries import choose_object
from engine.casting import CastingError, cast_spell
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Supertype, Zone


class BilboThiefintheNight(Creature):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Bilbo, Thief in the Night',
            'mana_cost': ManaCost.parse('{1}{U}'),
            'rules_text': 'Spells you cast from anywhere other than your hand cost {1} less to cast.\nWhenever Bilbo attacks, you may cast an artifact, instant, or sorcery spell from your graveyard. If an instant or sorcery spell cast this way would be put into your graveyard, exile it instead.',
            'base_power': 2,
            'base_toughness': 2,
            'subtypes': {'Halfling', 'Rogue'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def spell_cost_reduction(self, game, spell, caster):
        return int(caster is self.controller and getattr(spell, 'cast_from_zone', Zone.HAND) != Zone.HAND)

    def register_triggers(self, game):
        def effect(g, controller):
            candidates = []
            for card in controller.zones[Zone.GRAVEYARD].get_all():
                if not card.card_types & {CardType.ARTIFACT, CardType.INSTANT, CardType.SORCERY}:
                    continue
                candidates.append(card)
            chosen = choose_object(g, controller, candidates, 'Cast a spell from your graveyard',
                                   source_card=self, optional=True)
            if chosen is not None:
                departure = Zone.EXILE if chosen.card_types & {CardType.INSTANT, CardType.SORCERY} else None
                try:
                    cast_spell(g, controller, chosen, from_zone=Zone.GRAVEYARD,
                               ignore_timing=True, departure_zone=departure)
                except CastingError:
                    pass
        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent, source=self, controller=self.controller,
            condition=lambda g, event: event.creature is self or event.attacker is self,
            effect=effect))
