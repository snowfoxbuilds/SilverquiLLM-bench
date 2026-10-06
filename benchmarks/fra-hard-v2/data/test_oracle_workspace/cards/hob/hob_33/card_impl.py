from engine import attempts
from engine.card import Creature
from engine.card_queries import choose_object
from engine.casting import CastingError, cast_spell, grant_cast_permission
from engine.events import AttacksTriggeredEvent
from engine.faces import choose_face, faces_of, presented, whole_card
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Supertype, Zone

# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BilboThiefInTheNightAbility1:
    text = 'Spells you cast from anywhere other than your hand cost {1} less to cast.'


class BilboThiefInTheNightAbility2:
    text = 'Whenever Bilbo attacks, you may cast an artifact, instant, or sorcery spell from your graveyard. If an instant or sorcery spell cast this way would be put into your graveyard, exile it instead.'


# endregion Printed abilities


def _castable_by_trigger(face):
    return bool(face.card_types & {CardType.ARTIFACT, CardType.INSTANT, CardType.SORCERY})


class BilboThiefInTheNight(Creature):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Bilbo, Thief in the Night',
            'mana_cost': ManaCost.parse('{1}{U}'),
            'rules_text': 'Spells you cast from anywhere other than your hand cost {1} less to cast.\nWhenever Bilbo attacks, you may cast an artifact, instant, or sorcery spell from your graveyard. If an instant or sorcery spell cast this way would be put into your graveyard, exile it instead.',
            'base_power': 2,
            'base_toughness': 2,
            'subtypes': {'Halfling', 'Rogue'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def spell_cost_reduction(self, game, spell, caster):
        return int(caster is self.controller and getattr(spell, 'cast_from_zone', Zone.HAND) != Zone.HAND)

    def register_triggers(self, game):
        def effect(g, controller):
            graveyard = controller.zones[Zone.GRAVEYARD]

            def cast():
                cards = [card for card in graveyard.get_all()
                         if any(_castable_by_trigger(face) for face in faces_of(card))]
                chosen = choose_object(g, controller, presented(cards, _castable_by_trigger),
                                       'Cast a spell from your graveyard', source_card=self, optional=True)
                if chosen is None:
                    return None
                face = choose_face(g, controller, chosen, _castable_by_trigger)
                exile_instead = bool(face.card_types & {CardType.INSTANT, CardType.SORCERY})
                # The permission lasts only for this cast.
                grant_cast_permission(g, controller, whole_card(face), from_zone=Zone.GRAVEYARD)
                permission = g.cast_permissions[-1]
                try:
                    return cast_spell(g, controller, face, from_zone=Zone.GRAVEYARD, ignore_timing=True,
                                      departure_zone=Zone.EXILE if exile_instead else None)
                finally:
                    if permission in g.cast_permissions:
                        g.cast_permissions.remove(permission)

            # The cast is its own attempt: a rejected one is undone and asked again (see ADR-017).
            try:
                attempts.attempt(g, cast)
            except CastingError:
                # No player could have chosen differently: the spell is not cast.
                pass

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent, source=self, controller=self.controller,
            condition=lambda g, event: event.creature is self or event.attacker is self,
            effect=effect, printed=BilboThiefInTheNightAbility2))
