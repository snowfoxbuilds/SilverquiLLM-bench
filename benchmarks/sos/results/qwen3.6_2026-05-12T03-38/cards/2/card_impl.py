from engine.card import *
from engine.types import *


class RancorousArchaic(Creature):
    """Rancorous Archaic - {5} - 2/2 Avatar - Trample, Reach, Converge.

    Converge — This creature enters with a +1/+1 counter on it for each
    color of mana spent to cast it.
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="Rancorous Archaic",
            mana_cost=ManaCost.parse("{5}"),
            card_types={CardType.CREATURE},
            subtypes={"Avatar"},
            rules_text="""Trample, reach
Converge — This creature enters with a +1/+1 counter on it for each color of mana spent to cast it.""",
            base_power=2,
            base_toughness=2,
            keywords=Keyword.TRAMPLE | Keyword.REACH,
            **kwargs,
        )

    def on_resolve(self, game):
        colors_spent = getattr(self, "colors_spent", None)
        if colors_spent:
            num_counters = len(set(colors_spent))
            if num_counters:
                self.plus_one_counters = num_counters
