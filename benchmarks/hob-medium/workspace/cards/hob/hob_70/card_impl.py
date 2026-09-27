from engine.card import Creature
from engine.types import ManaCost, Supertype


class GollumRiddleMaster(Creature):
    """Implementation task: see card_spec.json and instructions.md."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Gollum, Riddle Master",
            "mana_cost": ManaCost.parse("{1}{B}"),
            "rules_text": "As Gollum enters, choose odd or even. (Zero is even.)\nWhenever an opponent casts a spell with mana value of the chosen quality, choose one that hasn't been chosen —\n• Put a +1/+1 counter on Gollum.\n• Each opponent loses 2 life and you gain 2 life.\n• Draw a card.",
            "base_power": 3,
            "base_toughness": 1,
            "subtypes": {"Halfling", "Horror"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
