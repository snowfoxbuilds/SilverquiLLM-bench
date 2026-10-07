from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class EmrakulTheExigentDoomAbility1:
    text = 'When you cast this spell, untap all lands you control.'


class EmrakulTheExigentDoomAbility2:
    text = 'Flying'


class EmrakulTheExigentDoomAbility3:
    text = 'trample'


class EmrakulTheExigentDoomAbility4:
    text = 'Ward—Sacrifice three permanents.'


class EmrakulTheExigentDoomAbility5:
    text = '{3}, Exile this card from your hand: Target land gains "{T}: Add {C}{C}" until this card is cast from exile. You may cast this card for as long as it remains exiled.'


# endregion Printed abilities


class EmrakulTheExigentDoom(Creature):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Emrakul, the Exigent Doom',
            'mana_cost': ManaCost.parse('{10}'),
            'card_types': {CardType.CREATURE},
            'rules_text': 'When you cast this spell, untap all lands you control.\nFlying, trample\nWard—Sacrifice three permanents.\n{3}, Exile this card from your hand: Target land gains "{T}: Add {C}{C}" until this card is cast from exile. You may cast this card for as long as it remains exiled.',
            'base_power': 12,
            'base_toughness': 12,
            'subtypes': {'Eldrazi'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
