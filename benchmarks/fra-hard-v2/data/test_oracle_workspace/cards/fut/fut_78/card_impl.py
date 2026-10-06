from engine.card import Instant
from engine.card_queries import query_yes_no
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import destroy
from engine.protection import get_colors
from engine.triggers import register_delayed_trigger
from engine.types import CardType, Color, ManaCost, TargetRequirement, Zone

# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SlaughterPactAbility1:
    text = 'Destroy target nonblack creature.'


class SlaughterPactAbility2:
    text = "At the beginning of your next upkeep, pay {2}{B}. If you don't, you lose the game."


# endregion Printed abilities


UPKEEP_COST = ManaCost.parse('{2}{B}')


def _nonblack_creature(obj) -> bool:
    return CardType.CREATURE in getattr(obj, 'card_types', ()) and Color.BLACK not in get_colors(obj)


class SlaughterPact(Instant):
    def __init__(self, **kwargs):
        defaults = {
            'name': 'Slaughter Pact',
            'mana_cost': ManaCost.parse('{0}'),
            'card_types': {CardType.INSTANT},
            'rules_text': "Destroy target nonblack creature.\nAt the beginning of your next upkeep, pay {2}{B}. If you don't, you lose the game.",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
        # Its color indicator makes it black though its mana cost has no colored mana (rule 204).
        self.colors = {Color.BLACK}

    def get_targets(self, game):
        return [TargetRequirement(filter_fn=_nonblack_creature, description='target nonblack creature',
                                  zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game):
        chosen = getattr(self, 'chosen_targets', None) or []
        target = chosen[0] if chosen else None
        legal = target is not None and _nonblack_creature(target) and any(
            game.get_battlefield(player).contains(target) for player in game.players)
        if not legal:
            # A spell whose only target is illegal does not resolve (rule 608.2b), so no pact is made.
            return
        destroy(game, target)
        controller = self.controller

        def pay_or_lose(state):
            pool = controller.mana_pool
            if pool.can_pay(UPKEEP_COST) and query_yes_no(state, controller, 'Pay {2}{B}?', source_card=self):
                pool.pay(UPKEEP_COST)
                return
            controller.has_lost = True

        register_delayed_trigger(
            game, BeginningOfUpkeepTriggeredEvent, controller, pay_or_lose,
            condition=lambda state, _event: state.active_player is controller,
            name='Slaughter Pact upkeep', printed=SlaughterPactAbility2,
        )
