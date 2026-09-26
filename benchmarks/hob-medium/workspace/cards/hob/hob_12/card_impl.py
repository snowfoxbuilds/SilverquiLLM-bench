from engine.card import Instant
from engine.types import ManaCost


class TheEaglesAreComing(Instant):
    """Implementation task: see card_spec.json and instructions.md."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "The Eagles Are Coming!",
            "mana_cost": ManaCost.parse("{1}{W}"),
            "rules_text": "Kicker {2}{W}{W} (You may pay an additional {2}{W}{W} as you cast this spell.)\nChoose target creature you own. If this spell was kicked, instead choose any number of target creatures you own. Return each chosen creature to your hand. At the beginning of the next upkeep, create a 4/4 white Bird Soldier creature token with flying for each creature returned to your hand this way.",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
