from engine.card import Instant
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SupperForSpidersAbility1:
    text = 'Put onto the battlefield under your control all creature cards in your opponents\' graveyards that were put there from the battlefield this turn. They are Food artifacts with "{2}, {T}, Sacrifice this artifact: You gain 3 life." (They lose all other types and subtypes.)'


# endregion Printed abilities


class SupperForSpiders(Instant):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Supper for Spiders',
            'mana_cost': ManaCost.parse('{1}{B}'),
            'card_types': {CardType.INSTANT},
            'rules_text': 'Put onto the battlefield under your control all creature cards in your opponents\' graveyards that were put there from the battlefield this turn. They are Food artifacts with "{2}, {T}, Sacrifice this artifact: You gain 3 life." (They lose all other types and subtypes.)',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
