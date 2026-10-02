from engine.card import Equipment
from engine.card_queries import query_yes_no
from engine.types import CardType, ManaCost, Supertype, Zone
from engine.zones import move_to_zone


class GlamdringFoehammer(Equipment):

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

    def choose_cast_face(self, game, player, mana_value_limit=None):
        from engine.casting import _permission
        self.restore_front_face()
        permission = _permission(game, player, self)
        if (not (permission and permission['normal_face_only']) and
                (mana_value_limit is None or mana_value_limit >= 4) and query_yes_no(
                game, player, 'Cast Gleam of Death Adventure?', source_card=self)):
            self.casting_adventure = True
            self.name = 'Gleam of Death'
            self.mana_cost = ManaCost.parse('{3}{U}')
            self.card_types = {CardType.SORCERY}
            self.subtypes = {'Adventure'}
            self.supertypes = set()

    def restore_front_face(self):
        self.casting_adventure = False
        self.name = 'Glamdring, Foe-hammer'
        self.mana_cost = ManaCost.parse('{2}')
        self.card_types = {CardType.ARTIFACT}
        self.subtypes = {'Equipment'}
        self.supertypes = {Supertype.LEGENDARY}

    def on_resolve(self, game):
        if not getattr(self, 'casting_adventure', False):
            return
        cards = self.controller.zones[Zone.LIBRARY].top(6)
        for card in cards:
            move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
        for card in cards:
            if (self.controller.zones[Zone.GRAVEYARD].contains(card) and
                    card.card_types & {CardType.INSTANT, CardType.SORCERY}):
                move_to_zone(game, card, Zone.GRAVEYARD, Zone.HAND)

    def spell_cost_reduction(self, game, spell, caster):
        if (caster is self.controller and self.is_equip_active(game) and
                spell.card_types & {CardType.INSTANT, CardType.SORCERY}):
            return max(0, self.attached_to.power)
        return 0
