from engine.card import Creature
from engine.types import ManaCost, Supertype


class ElrondMoonReader(Creature):
    """Implementation task: see card_spec.json and instructions.md."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Elrond, Moon-Reader",
            "mana_cost": ManaCost.parse("{2}{U}"),
            "rules_text": "Whenever you activate an ability of a creature, draw a card. This ability triggers only once each turn.\n{5}{U}{U}: Exile up to two other target nonland permanents you control. Return those cards to the battlefield under their owner's control at the beginning of the next end step.",
            "base_power": 3,
            "base_toughness": 3,
            "subtypes": {"Elf", "Noble"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
