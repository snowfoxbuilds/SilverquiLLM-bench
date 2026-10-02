from engine.abilities import tap_cost
from engine.card import ActivatedAbility, Land, ManaAbility
from engine.card_queries import choose_object
from engine.copying import become_copy
from engine.protection import has_protection_from
from engine.stack import same_stint, surviving_targets
from engine.types import CardType, ManaCost, ManaType


class HallofEchoes(Land):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Hall of Echoes',
            'mana_cost': ManaCost(),
            'rules_text': '{T}: Add {C}.\n{5}: This land becomes a copy of target creature you control until end of turn. The "legend rule" doesn\'t apply to permanents you control this turn.',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
        self.summoning_sick = True

    def get_mana_abilities(self):
        return [ManaAbility(tap_cost,
                            lambda game: self.controller.mana_pool.add(ManaType.COLORLESS, 1),
                            "{T}: Add {C}.")]

    def get_activated_abilities(self):
        def legal_target(state, card, player):
            return (state.get_battlefield(player).contains(card)
                    and card.controller is player and CardType.CREATURE in card.card_types
                    and not has_protection_from(card, self))

        def targeting(state, source, player):
            options = [card for card in state.get_battlefield(player).get_all()
                       if legal_target(state, card, player)]
            if not options:
                return None
            return [choose_object(state, player, options, "Target creature you control", source_card=self)]

        def cost(state, source):
            mana = ManaCost(generic=5)
            if not source.controller.mana_pool.can_pay(mana):
                return False
            source.controller.mana_pool.pay(mana)
            return True

        def effect(state, targets, context):
            targets = surviving_targets(state, context, targets,
                lambda card: legal_target(state, card, context.controller))
            if not targets:
                return
            context.controller.legend_rule_suppressed = True
            if same_stint(state, self, context.source_instance_id):
                become_copy(state, self, targets[0])

        return [ActivatedAbility(cost, effect, "{5}: Copy target creature until end of turn",
            targeting, lambda state, source, player: state.get_battlefield(player).contains(source)
            and source.controller is player)]
