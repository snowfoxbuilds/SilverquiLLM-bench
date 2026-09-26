from engine.card import CardImpl
from engine.card_queries import choose_object
from engine.continuous_effects import ContinuousEffect, Layer
from engine.stack import object_current_zone, object_stint_id
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, Zone


def on_battlefield(game, card):
    return any(game.get_battlefield(p).contains(card) for p in game.players)


def delayed(game, event_type, controller, effect):
    marker = CardImpl(name="Delayed trigger", owner=controller)

    def once(g, event):
        g.trigger_manager.unregister(marker)
        return True

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=event_type,
            condition=once,
            effect=effect,
            source=marker,
            controller=controller,
        )
    )


def choose_targets(game, source, controller, predicate, maximum):
    from engine.protection import has_protection_from

    candidates = [
        c
        for p in game.players
        for c in game.get_battlefield(p).get_all()
        if predicate(c) and not has_protection_from(c, source)
    ]
    chosen = choose_object(
        game,
        controller,
        candidates,
        "Choose targets",
        source_card=source,
        min=0,
        max=maximum,
        optional=True,
    )
    return chosen if isinstance(chosen, list) else ([] if chosen is None else [chosen])


def return_from_exile(game, tracked):
    from engine.zones import move_to_zone

    for card, stint in tracked:
        if (
            not getattr(card, "is_token", False)
            and object_current_zone(game, card) == "exile"
            and object_stint_id(game, card) == stint
        ):
            card.controller = card.owner
            reset_entry_state(game, card)
            move_to_zone(game, card, Zone.EXILE, Zone.BATTLEFIELD)


def reset_entry_state(game, card):
    from engine.game import remove_counter

    for kind, count in list(card.counters.items()):
        remove_counter(game, card, kind, count)
    if hasattr(card, "summoning_sick"):
        card.summoning_sick = True
        card.damage_marked = 0
    if hasattr(card, "is_tapped"):
        card.is_tapped = False


def artifact_entry(game, card):
    reset_entry_state(game, card)
    card._entry_characteristic_defaults = {
        "card_types": frozenset(card.card_types),
        "subtypes": frozenset(card.subtypes),
    }

    def apply(g):
        card.card_types = {CardType.ARTIFACT}
        card.subtypes = set()

    apply(game)
    game.effect_manager.add(ContinuousEffect(source=card, layer=Layer.TYPE, apply=apply))


def tap_for_mana(game, source):
    from engine.abilities import tap_cost

    if not on_battlefield(game, source):
        return False
    if (
        CardType.CREATURE in source.card_types
        and source.summoning_sick
        and not source.keywords & Keyword.HASTE
    ):
        return False
    return tap_cost(game, source)
