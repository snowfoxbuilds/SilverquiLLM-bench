from engine.card import Creature
from engine.types import ManaCost, Supertype


class TomBertAndWilliam(Creature):
    """Implementation task: see card_spec.json and instructions.md."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Tom, Bert, and William",
            "mana_cost": ManaCost.parse("{3}{B}{G}"),
            "rules_text": "{1}, Sacrifice another creature: Draw cards equal to the sacrificed creature's power, then discard a card.\nWhen Tom, Bert, and William die, if they were a creature, return them to the battlefield. They're an artifact. (They're no longer a creature.)",
            "base_power": 5,
            "base_toughness": 5,
            "subtypes": {"Troll"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
