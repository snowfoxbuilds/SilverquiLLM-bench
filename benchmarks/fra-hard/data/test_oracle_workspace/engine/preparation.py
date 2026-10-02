"""Prepared designations and their linked exiled spell copies (rule 722)."""

from engine.casting import grant_cast_permission
from engine.types import Zone


def clear_preparation(game, card):
    card.prepared = False
    spell = getattr(card, "prepared_copy", None)
    if spell is not None:
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
    grant_cast_permission(game, card.controller, spell, controller_source=card)


def consume_preparation(game, spell):
    source = getattr(spell, "prepared_source", None)
    if source is not None:
        source.prepared = False
        source.prepared_copy = None
