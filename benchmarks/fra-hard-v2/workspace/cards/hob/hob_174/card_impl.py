from engine.card import Artifact, Sorcery
from engine.types import CardType, ManaCost, Supertype


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class GlamdringFoehammerAbility1:
    text = "Instant and sorcery spells you cast cost {X} less to cast, where X is equipped creature's power."


class GlamdringFoehammerAbility2:
    text = 'Equip {2}'


class GleamOfDeathAbility1:
    text = 'Mill six cards, then put all instant and sorcery cards from among them into your hand. (Then exile this card. You may cast the artifact later from exile.)'


# endregion Printed abilities


class GlamdringFoehammer(Artifact):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Glamdring, Foe-hammer',
            'mana_cost': ManaCost.parse('{2}'),
            'card_types': {CardType.ARTIFACT},
            'rules_text': "Instant and sorcery spells you cast cost {X} less to cast, where X is equipped creature's power.\nEquip {2}",
            'subtypes': {'Equipment'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class GleamOfDeath(Sorcery):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Gleam of Death',
            'mana_cost': ManaCost.parse('{3}{U}'),
            'card_types': {CardType.SORCERY},
            'rules_text': 'Mill six cards, then put all instant and sorcery cards from among them into your hand. (Then exile this card. You may cast the artifact later from exile.)',
            'subtypes': {'Adventure'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
