"""Prepared designations and the spell copies they let their controller cast.

As a permanent becomes prepared, its controller creates a copy of its prepare
spell in exile, which stays there while the permanent stays on the battlefield
prepared, and which the permanent's controller may cast (rule 722.3c). The copy
is numbered as it is made, like any copy.
"""

from engine.casting import grant_cast_permission
from engine.types import Zone


def clear_preparation(game, card):
    card.prepared = False
    spell = getattr(card, "prepared_copy", None)
    if spell is not None:
        # Outside the stack, a copy of a card ceases to exist (rule 704.5e).
        for player in game.players:
            zone = player.zones[Zone.EXILE]
            if zone.contains(spell):
                zone.remove(spell)
    card.prepared_copy = None


def prepare(game, card, factory):
    if getattr(card, "prepared", False):
        return
    if not any(game.get_battlefield(player).contains(card) for player in game.players):
        return
    card.prepared = True
    spell = factory(owner=card.controller, controller=card.controller)
    spell.is_card_copy = True
    spell.prepared_source = card
    card.prepared_copy = spell
    card.controller.zones[Zone.EXILE].add(spell)
    game.created_copies.append(spell)
    grant_cast_permission(game, card.controller, spell, from_zone=Zone.EXILE, controller_source=card)


def consume_preparation(game, spell):
    # Casting the copy unprepares its permanent (rule 722.3c).
    source = getattr(spell, "prepared_source", None)
    if source is not None:
        source.prepared = False
        source.prepared_copy = None
