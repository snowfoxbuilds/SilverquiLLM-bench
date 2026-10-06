"""Copiable characteristics exclude counters and continuous modifications."""

from copy import copy

from engine.card import Creature, GameObject
from engine.types import CardType

CHARACTERISTICS = ("name", "mana_cost", "rules_text", "card_types", "subtypes", "supertypes",
                   "keywords", "base_power", "base_toughness", "starting_loyalty", "colors",
                   "_original_card_types", "_original_keywords")


def copiable_values(card):
    values = {key: copy(getattr(card, key)) for key in CHARACTERISTICS if hasattr(card, key)}
    values["card_types"] = set(card._original_card_types)
    values["keywords"] = card._original_keywords
    return values


def copy_card(card, player):
    result = copy(card)
    result.__dict__ = {key: copy(value) for key, value in card.__dict__.items()
                       if not key.startswith(("_printed_", "_copy_"))
                       and key not in ("get_loyalty_abilities", "get_mana_abilities", "_game")}
    result.__dict__.update(copiable_values(card))
    result.object_id = GameObject._next_id
    GameObject._next_id += 1
    result.owner = result.controller = player
    result._generic_counters = {}
    result.is_card_copy = True
    result.is_token = False
    result.was_cast = False
    result.prepared = False
    result.prepared_copy = None
    result.plus_one_counters = result.minus_one_counters = result.damage_marked = 0
    result._base_plus_one_counters = result._base_minus_one_counters = 0
    result.is_tapped = result.is_attacking = result.is_blocking = False
    result.summoning_sick = True
    if hasattr(result, "starting_loyalty"):
        result.loyalty = result.starting_loyalty
    result._reset_characteristics()
    return result


def become_copy(game, card, target):
    if not hasattr(card, "_copy_original_class"):
        card._copy_original_class = type(card)
        card._copy_original_values = copiable_values(card)
        card._copy_object_id = card.object_id
    game.trigger_manager.unregister(card)
    try:
        printed = type(target)()
    except TypeError:
        printed = None
    if printed is not None:
        for key, value in printed.__dict__.items():
            if key not in card.__dict__:
                card.__dict__[key] = copy(value)
    card.__class__ = type(target)
    card.__dict__.update(copiable_values(target))
    for name in ("_printed_loyalty_method", "get_loyalty_abilities", "_printed_mana_method", "get_mana_abilities"):
        card.__dict__.pop(name, None)
    if CardType.CREATURE in card.card_types:
        for key, value in Creature().__dict__.items():
            if key not in card.__dict__:
                card.__dict__[key] = value
        for counter, attribute in (("+1/+1", "plus_one_counters"), ("-1/-1", "minus_one_counters")):
            amount = card._generic_counters.pop(counter, 0)
            setattr(card, attribute, getattr(card, attribute) + amount)
            setattr(card, "_base_" + attribute, getattr(card, attribute))
    card._reset_characteristics()
    card.register_triggers(game)
    card.register_replacement_effects(game)


def end_copy(card, game):
    if not hasattr(card, "_copy_original_class"):
        return
    if card.__dict__.get("_copy_object_id") != card.object_id:
        # A token copy of a permanent that was a copy copied what that
        # permanent copied (rule 707.3); the copy effect ending is not its own.
        for name in ("_copy_original_class", "_copy_original_values", "_copy_object_id"):
            card.__dict__.pop(name, None)
        return
    game.trigger_manager.unregister(card)
    game.replacement_manager.unregister(card)
    original = card._copy_original_values
    card.__class__ = card._copy_original_class
    for key in CHARACTERISTICS:
        card.__dict__.pop(key, None)
    card.__dict__.update(original)
    if CardType.CREATURE not in card.card_types:
        for counter, attribute in (("+1/+1", "plus_one_counters"), ("-1/-1", "minus_one_counters")):
            amount = getattr(card, attribute, 0)
            if amount:
                card._generic_counters[counter] = amount
            card.__dict__.pop(attribute, None)
            card.__dict__.pop("_base_" + attribute, None)
    for name in ("_copy_original_class", "_copy_original_values", "_copy_object_id", "_printed_loyalty_method",
                 "get_loyalty_abilities", "_printed_mana_method", "get_mana_abilities"):
        card.__dict__.pop(name, None)
    card._reset_characteristics()


def refresh_copies(game):
    for player in game.players:
        player.legend_rule_suppressed = False
        for card in game.get_battlefield(player).get_all():
            end_copy(card, game)
