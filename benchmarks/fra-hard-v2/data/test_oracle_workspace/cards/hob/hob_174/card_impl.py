from engine.card import Equipment, Sorcery
from engine.types import CardType, ManaCost, Supertype, Zone
from engine.zones import move_to_zone

# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class GlamdringFoehammerAbility1:
    text = "Instant and sorcery spells you cast cost {X} less to cast, where X is equipped creature's power."


class GlamdringFoehammerAbility2:
    text = 'Equip {2}'


class GleamOfDeathAbility1:
    text = 'Mill six cards, then put all instant and sorcery cards from among them into your hand. (Then exile this card. You may cast the artifact later from exile.)'


# endregion Printed abilities


class GleamOfDeath(Sorcery):
    """Glamdring's Adventure face: an object of its own that stands for the card
    while it is cast and on the stack (see engine.faces)."""

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Gleam of Death',
            'mana_cost': ManaCost.parse('{3}{U}'),
            'rules_text': 'Mill six cards, then put all instant and sorcery cards from among them into your hand. (Then exile this card. You may cast the artifact later from exile.)',
            'subtypes': {'Adventure'},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def on_resolve(self, game):
        library = self.controller.zones[Zone.LIBRARY]
        milled = library.top(6)
        for card in milled:
            move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
        graveyard = self.controller.zones[Zone.GRAVEYARD]
        for card in milled:
            if graveyard.contains(card) and card.card_types & {CardType.INSTANT, CardType.SORCERY}:
                move_to_zone(game, card, Zone.GRAVEYARD, Zone.HAND)


class GlamdringFoehammer(Equipment):

    equip_printed = GlamdringFoehammerAbility2

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Glamdring, Foe-hammer',
            'mana_cost': ManaCost.parse('{2}'),
            'rules_text': "Instant and sorcery spells you cast cost {X} less to cast, where X is equipped creature's power.\nEquip {2}",
            'subtypes': {'Equipment'},
            'supertypes': {Supertype.LEGENDARY},
            'equip_cost': ManaCost.parse('{2}'),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def faces(self):
        face = getattr(self, 'adventure_face', None)
        if face is None or face.whole_card is not self:
            face = GleamOfDeath()
            face.whole_card = self
            self.adventure_face = face
        face.owner = self.owner
        face.controller = self.controller
        face.is_card_copy = getattr(self, 'is_card_copy', False)
        return [self, face]

    def spell_cost_reduction(self, game, spell, caster):
        if (caster is self.controller and self.is_equip_active(game) and
                spell.card_types & {CardType.INSTANT, CardType.SORCERY}):
            return max(0, self.attached_to.power)
        return 0
