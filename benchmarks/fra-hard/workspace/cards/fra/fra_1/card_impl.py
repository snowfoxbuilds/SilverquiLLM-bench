from engine.card import Creature
from engine.types import ManaCost, Supertype


class EmrakultheExigentDoom(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Emrakul, the Exigent Doom',
            'mana_cost': ManaCost.parse('{10}'),
            'rules_text': 'When you cast this spell, untap all lands you control.\nFlying, trample\nWard—Sacrifice three permanents.\n{3}, Exile this card from your hand: Target land gains "{T}: Add {C}{C}" until this card is cast from exile. You may cast this card for as long as it remains exiled.',
            'base_power': 12,
            'base_toughness': 12,
            'subtypes': {'Eldrazi'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
