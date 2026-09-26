"""Goldvein Pick grants its equip bonus and creates Treasure through combat."""

from cards.fdn.fdn_253.card_impl import GoldveinPick
from engine.card import Creature, Equipment
from engine.combat import combat_damage_step
from engine.types import ManaCost, ManaType
from test_utils import (
    activate_card_ability,
    behavioral_game,
    declare_attackers,
    declare_blockers,
    enter_permanent,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def arrange():
    game = behavioral_game()
    player = game.players[0]
    bear = put_on_battlefield(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    bear.summoning_sick = False
    pick = enter_permanent(game, player, GoldveinPick())
    player.mana_pool.add(ManaType.COLORLESS, 1)
    prefer(player, object_preference(game, bear))
    activate_card_ability(game, player, pick)
    resolve_stack(game)
    return game, player, bear, pick


def test_static_data():
    card = GoldveinPick()
    assert card.name == "Goldvein Pick" and card.mana_cost == ManaCost.parse("{2}")
    assert isinstance(card, Equipment) and card.equip_cost == ManaCost.parse("{1}")


def test_grants_plus_one_plus_one():
    _game, player, bear, pick = arrange()
    assert (bear.power, bear.toughness) == (3, 3) and pick.attached_to is bear
    assert player.mana_pool.total() == 0


def test_combat_damage_to_player_makes_treasure():
    game, player, bear, _pick = arrange()
    declare_attackers(game, [bear.name])
    declare_blockers(game, {})
    combat_damage_step(game)
    resolve_stack(game)
    assert game.players[1].life == 17
    tokens = [c for c in game.get_battlefield(player).get_all() if getattr(c, "is_token", False)]
    assert len(tokens) == 1 and "Treasure" in tokens[0].subtypes
