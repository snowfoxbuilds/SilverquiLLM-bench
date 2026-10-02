"""Mana abilities granted for a linked, non-turn duration."""

from engine.abilities import tap_cost
from engine.card import ManaAbility
from engine.types import CardType, ManaType, Zone


def grant_double_colorless(game, land, source, exile_epoch):
    grant = {"land": land, "land_epoch": game.refs.zone_epoch(land),
                 "source": source, "exile_epoch": exile_epoch, "active": True}
    if not hasattr(game, "linked_mana_grants"):
        game.linked_mana_grants = []
    game.linked_mana_grants.append(grant)
    refresh_mana_grants(game)


def refresh_mana_grants(game):
    for grant in getattr(game, "linked_mana_grants", []):
        land = grant["land"]
        if hasattr(land, "_printed_mana_method"):
            continue
        land._printed_mana_method = getattr(land, "get_mana_abilities", list)

        def abilities(land=land):
            result = land._printed_mana_method()
            for item in getattr(game, "linked_mana_grants", []):
                if (item["land"] is not land or not item["active"]
                        or game.refs.zone_epoch(land) != item["land_epoch"]):
                    continue

                def cost(state, source):
                    if CardType.CREATURE in source.card_types and source.summoning_sick:
                        return False
                    return any(state.get_battlefield(p).contains(source) for p in state.players) and tap_cost(state, source)

                result.append(ManaAbility(cost,
                    lambda state: land.controller.mana_pool.add(ManaType.COLORLESS, 2),
                    "{T}: Add {C}{C}."))
            return result

        land.get_mana_abilities = abilities


def end_exile_duration(game, source):
    if getattr(source, "cast_from_zone", None) != Zone.EXILE:
        return
    for grant in getattr(game, "linked_mana_grants", []):
        if grant["source"] is source and grant["exile_epoch"] == game.refs.zone_epoch(source):
            grant["active"] = False
