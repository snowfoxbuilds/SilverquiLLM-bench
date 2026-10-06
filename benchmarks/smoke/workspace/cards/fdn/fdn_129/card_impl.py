from engine.card import Artifact
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class LeylineAxeAbility1:
    text = 'If this card is in your opening hand, you may begin the game with it on the battlefield.'


class LeylineAxeAbility2:
    text = 'Equipped creature gets +1/+1 and has double strike and trample.'


class LeylineAxeAbility3:
    text = 'Equip {3} ({3}: Attach to target creature you control. Equip only as a sorcery.)'


# endregion Printed abilities


class LeylineAxe(Artifact):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Leyline Axe',
            'mana_cost': ManaCost.parse('{4}'),
            'card_types': {CardType.ARTIFACT},
            'rules_text': 'If this card is in your opening hand, you may begin the game with it on the battlefield.\nEquipped creature gets +1/+1 and has double strike and trample.\nEquip {3} ({3}: Attach to target creature you control. Equip only as a sorcery.)',
            'subtypes': {'Equipment'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
