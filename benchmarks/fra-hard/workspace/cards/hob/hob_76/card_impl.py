from engine.card import Sorcery
from engine.types import ManaCost, Supertype


class InsideInformation(Sorcery):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Inside Information',
            'mana_cost': ManaCost.parse('{X}{B}{B}'),
            'rules_text': "Exile the top X cards of target opponent's library. You may play those cards this turn. If you cast a spell this way, pay life equal to its mana value rather than pay its mana cost.",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
