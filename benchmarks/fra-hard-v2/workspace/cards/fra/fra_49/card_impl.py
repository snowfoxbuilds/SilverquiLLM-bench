from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BloodlineRecollectorAbility1:
    text = "At the beginning of each end step, if three or more creatures died this turn, this creature becomes prepared. (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)"


class AncestralCravingAbility1:
    text = 'Target player draws three cards and loses 3 life.'


# endregion Printed abilities


class BloodlineRecollector(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Bloodline Recollector',
            'mana_cost': ManaCost.parse('{1}{B}'),
            'card_types': {CardType.CREATURE},
            'rules_text': "At the beginning of each end step, if three or more creatures died this turn, this creature becomes prepared. (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)",
            'base_power': 2,
            'base_toughness': 2,
            'subtypes': {'Vampire', 'Warlock'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class AncestralCraving(Instant):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Ancestral Craving',
            'mana_cost': ManaCost.parse('{B}'),
            'card_types': {CardType.INSTANT},
            'rules_text': 'Target player draws three cards and loses 3 life.',
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
