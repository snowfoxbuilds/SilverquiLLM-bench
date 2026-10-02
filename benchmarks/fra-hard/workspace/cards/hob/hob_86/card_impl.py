from engine.card import Instant
from engine.types import ManaCost, Supertype


class SupperforSpiders(Instant):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Supper for Spiders',
            'mana_cost': ManaCost.parse('{1}{B}'),
            'rules_text': 'Put onto the battlefield under your control all creature cards in your opponents\' graveyards that were put there from the battlefield this turn. They are Food artifacts with "{2}, {T}, Sacrifice this artifact: You gain 3 life." (They lose all other types and subtypes.)',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
