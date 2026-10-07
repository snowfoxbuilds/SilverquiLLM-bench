import inspect

from engine.card import ActivatedAbility, Instant
from engine.continuous_effects import ContinuousEffect, Layer
from engine.game import gain_life, sacrifice
from engine.types import CardType, ManaCost, Zone
from engine.zones import move_to_zone

# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SupperForSpidersAbility1:
    text = 'Put onto the battlefield under your control all creature cards in your opponents\' graveyards that were put there from the battlefield this turn. They are Food artifacts with "{2}, {T}, Sacrifice this artifact: You gain 3 life." (They lose all other types and subtypes.)'


# endregion Printed abilities


class SupperForSpiders(Instant):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Supper for Spiders',
            'mana_cost': ManaCost.parse('{1}{B}'),
            'rules_text': 'Put onto the battlefield under your control all creature cards in your opponents\' graveyards that were put there from the battlefield this turn. They are Food artifacts with "{2}, {T}, Sacrifice this artifact: You gain 3 life." (They lose all other types and subtypes.)',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def on_resolve(self, game):
        cards = [card for player in game.players if player is not self.controller
                 for card in player.zones[Zone.GRAVEYARD].get_all()
                 if CardType.CREATURE in card.card_types and not getattr(card, 'is_token', False)
                 and any(item is card and epoch == game.refs.zone_epoch(card) and turn == game.turn_number
                         for item, epoch, turn, creature in game.battlefield_deaths)]
        for card in cards:
            card.controller = self.controller
            original_subtypes = set(card.subtypes)
            original_getter = card.get_activated_abilities
            had_getter_override = 'get_activated_abilities' in card.__dict__

            def food_type(g, permanent=card):
                permanent.card_types = {CardType.ARTIFACT}
                permanent.subtypes = {'Food'}

            def cost(g, source):
                controller = source.controller
                mana = ManaCost(generic=2)
                if (not controller.zones[Zone.BATTLEFIELD].contains(source) or source.is_tapped
                        or not controller.mana_pool.can_pay(mana)):
                    return False
                controller.mana_pool.pay(mana)
                source.is_tapped = True
                sacrifice(g, controller, source)
                return True

            def abilities(*game_arg, original=original_getter):
                # The getter may be called with or without the game, like any card's.
                takes_game = bool(inspect.signature(original).parameters)
                return list(original(*game_arg) if takes_game else original()) + [ActivatedAbility(
                    cost=cost, targeting=lambda g, source, controller: [],
                    effect=lambda g, targets, context: gain_life(g, context.controller, 3),
                    description='{2}, {T}, Sacrifice: gain 3 life',
                    printed=SupperForSpidersAbility1)]

            card.get_activated_abilities = abilities

            def restore(permanent=card, getter=original_getter, subtypes=original_subtypes,
                        had_override=had_getter_override):
                if had_override:
                    permanent.get_activated_abilities = getter
                else:
                    permanent.__dict__.pop('get_activated_abilities', None)
                permanent.subtypes = set(subtypes)
                permanent.card_types = set(permanent._original_card_types)
            card.zone_departure_callbacks = [restore]
            game.effect_manager.add(ContinuousEffect(source=card, layer=Layer.TYPE, apply=food_type))
            food_type(game)
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)
