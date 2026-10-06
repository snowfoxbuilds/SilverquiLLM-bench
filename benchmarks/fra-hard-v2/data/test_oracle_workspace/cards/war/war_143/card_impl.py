from engine.card import CardImpl, LoyaltyAbility, Planeswalker
from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer, SubLayer
from engine.events import AttacksTriggeredEvent
from engine.game import create_token, deal_damage
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost, Supertype, Zone

from cards.fdn.tokens import make_creature_token

# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SarkhanTheMasterlessAbility1:
    text = 'Whenever a creature attacks you or a planeswalker you control, each Dragon you control deals 1 damage to that creature.'


class SarkhanTheMasterlessAbility2:
    text = '+1: Until end of turn, each planeswalker you control becomes a 4/4 red Dragon creature and gains flying.'


class SarkhanTheMasterlessAbility3:
    text = '−3: Create a 4/4 red Dragon creature token with flying.'


# endregion Printed abilities


def _controlled(game, player):
    """The permanents ``player`` controls, wherever the engine keeps them."""
    return [card for owner in game.players for card in owner.zones[Zone.BATTLEFIELD].get_all()
            if (getattr(card, 'controller', None) or owner) is player]


def _on_battlefield(game, card):
    return any(owner.zones[Zone.BATTLEFIELD].contains(card) for owner in game.players)


class SarkhanTheMasterless(Planeswalker):
    def __init__(self, **kwargs):
        defaults = {
            'name': 'Sarkhan the Masterless',
            'mana_cost': ManaCost.parse('{3}{R}{R}'),
            'card_types': {CardType.PLANESWALKER},
            'rules_text': 'Whenever a creature attacks you or a planeswalker you control, each Dragon you control deals 1 damage to that creature.\n+1: Until end of turn, each planeswalker you control becomes a 4/4 red Dragon creature and gains flying.\n−3: Create a 4/4 red Dragon creature token with flying.',
            'starting_loyalty': 5,
            'subtypes': {'Sarkhan'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def register_triggers(self, game):
        source = self

        def attacks_me(state, event):
            controller = source.controller
            defender = state.combat_state.attackers.get(event.attacker)
            if defender is None:
                return False
            if defender is controller:
                return True
            return (CardType.PLANESWALKER in getattr(defender, 'card_types', ())
                    and getattr(defender, 'controller', None) is controller)

        def capture(state, event, controller):
            return event.attacker

        def each_dragon_deals_one(state, controller, attacker):
            if not _on_battlefield(state, attacker):
                return
            dragons = [card for card in _controlled(state, controller)
                       if CardType.CREATURE in getattr(card, 'card_types', ()) and 'Dragon' in card.subtypes]
            for dragon in dragons:
                deal_damage(state, dragon, attacker, 1)

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent, condition=attacks_me, effect=each_dragon_deals_one,
            source=self, controller=self.controller, capture=capture, printed=SarkhanTheMasterlessAbility1,
        ))

    def get_loyalty_abilities(self):
        source = self

        def planeswalkers_become_dragons(game):
            controller = source.controller
            # The planeswalkers it affects are fixed as it resolves (rule 611.2c).
            walkers = [card for card in _controlled(game, controller)
                       if CardType.PLANESWALKER in getattr(card, 'card_types', ())
                       and callable(getattr(card, 'become_creature', None))]
            if not walkers:
                return
            effects = []
            # An effect of a resolved ability outlasts its source (rule 611.2a), so
            # it is not sourced by Sarkhan, whose departure removes what it sources.
            marker = CardImpl(name='Sarkhan the Masterless +1', owner=controller)

            def affected():
                return [card for card in effects[0].bound_to if _on_battlefield(game, card)]

            def become_dragons(_state):
                for card in affected():
                    card.become_creature('Dragon')

            def turn_red(_state):
                for card in affected():
                    card.set_colors({Color.RED})

            def gain_flying(_state):
                for card in affected():
                    card.keywords = (getattr(card, 'keywords', None) or Keyword(0)) | Keyword.FLYING

            def four_four(_state):
                for card in affected():
                    card.modified_power = card.modified_toughness = 4

            for layer, sublayer, apply in (
                (Layer.TYPE, None, become_dragons),
                (Layer.COLOR, None, turn_red),
                (Layer.ABILITY, None, gain_flying),
                (Layer.POWER_TOUGHNESS, SubLayer.SET_PT, four_four),
            ):
                effects.append(game.effect_manager.add(ContinuousEffect(
                    source=marker, layer=layer, sublayer=sublayer, apply=apply,
                    duration=DURATION_END_OF_TURN, bound_to=list(walkers),
                )))
            game.effect_manager.apply_all(game)

        def dragon_token(game):
            controller = source.controller
            create_token(game, controller, factory=lambda: make_creature_token(
                'Dragon', {'Dragon'}, [Color.RED], 4, 4, keywords=Keyword.FLYING))

        return [
            LoyaltyAbility(1, planeswalkers_become_dragons,
                           '+1: Until end of turn, each planeswalker you control becomes a 4/4 red Dragon creature and gains flying.',
                           printed=SarkhanTheMasterlessAbility2),
            LoyaltyAbility(-3, dragon_token, '−3: Create a 4/4 red Dragon creature token with flying.',
                           printed=SarkhanTheMasterlessAbility3),
        ]
