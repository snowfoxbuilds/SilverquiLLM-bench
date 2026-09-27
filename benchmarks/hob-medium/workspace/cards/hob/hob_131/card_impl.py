from engine.card import Creature
from engine.types import ManaCost, Supertype


class TheNotaryHobbits(Creature):
    """Implementation task: see card_spec.json and instructions.md."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "The Notary Hobbits",
            "mana_cost": ManaCost.parse("{3}{G}{G}"),
            "rules_text": "When The Notary Hobbits enter, if they're not a token, create two tokens that are copies of them, except the tokens aren't legendary.\n{T}: Add {C} for each Halfling you control.",
            "base_power": 1,
            "base_toughness": 1,
            "subtypes": {"Halfling", "Advisor"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
