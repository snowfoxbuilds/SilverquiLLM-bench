from engine.card import Sorcery
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class InsideInformationAbility1:
    text = "Exile the top X cards of target opponent's library. You may play those cards this turn. If you cast a spell this way, pay life equal to its mana value rather than pay its mana cost."


# endregion Printed abilities


class InsideInformation(Sorcery):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Inside Information',
            'mana_cost': ManaCost.parse('{X}{B}{B}'),
            'card_types': {CardType.SORCERY},
            'rules_text': "Exile the top X cards of target opponent's library. You may play those cards this turn. If you cast a spell this way, pay life equal to its mana value rather than pay its mana cost.",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
