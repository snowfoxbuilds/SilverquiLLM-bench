from engine.card import Artifact
from engine.types import ManaCost, Supertype


class GlamdringFoehammer(Artifact):
    """Implementation task: see card_spec.json."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Glamdring, Foe-hammer',
            'mana_cost': ManaCost.parse('{2}'),
            'rules_text': "Instant and sorcery spells you cast cost {X} less to cast, where X is equipped creature's power.\nEquip {2}",
            'subtypes': {'Equipment'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
