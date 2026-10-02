"""Celestial Armor uses paid equip or its actual cast/entry attachment."""

from cards.fdn.fdn_5.card_impl import CelestialArmor
from engine.card import Creature, Equipment
from engine.types import Keyword, ManaCost, ManaType, Phase, Step
from test_utils import (
    activate_card_ability,
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def test_static_data():
    card = CelestialArmor()
    assert card.name == "Celestial Armor" and card.mana_cost == ManaCost.parse("{2}{W}")
    assert card.equip_cost == ManaCost.parse("{3}{W}") and card.keywords & Keyword.FLASH
    assert isinstance(card, Equipment) and card.is_equipment


def test_static_buff_after_paid_equip():
    game = behavioral_game()
    player = game.players[0]
    bear = put_on_battlefield(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    armor = put_on_battlefield(game, player, CelestialArmor())
    player.mana_pool.add(ManaType.WHITE, 4)
    prefer(player, object_preference(game, bear))
    activate_card_ability(game, player, armor)
    resolve_stack(game)
    assert (bear.power, bear.toughness) == (4, 2) and bear.keywords & Keyword.FLYING
    assert player.mana_pool.total() == 0


def test_etb_attach_grants_protection_until_cleanup():
    game = behavioral_game()
    player = game.players[0]
    bear = put_on_battlefield(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    armor = CelestialArmor(owner=player)
    player.mana_pool.add(ManaType.WHITE, 3)
    prefer(player, object_preference(game, bear))
    cast_card(game, player, armor)
    assert armor.attached_to is bear
    assert bear.keywords & Keyword.FLYING and bear.keywords & Keyword.HEXPROOF
    assert bear.keywords & Keyword.INDESTRUCTIBLE
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    resolve_stack(game)
    assert not bear.keywords & (Keyword.HEXPROOF | Keyword.INDESTRUCTIBLE)
    assert bear.keywords & Keyword.FLYING and bear.power == 4
