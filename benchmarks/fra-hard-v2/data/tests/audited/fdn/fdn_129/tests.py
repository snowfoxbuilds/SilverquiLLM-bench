"""Leyline Axe attaches through paid equip activations and normal zone departures."""

import pytest
from cards.fdn.fdn_129.card_impl import LeylineAxe
from engine.abilities import AbilityError
from engine.card import Creature, Equipment, printed_class
from engine.game import destroy
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    behavioral_game,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def arrange(count=1, mana=3):
    game = behavioral_game()
    player = game.players[0]
    axe = put_on_battlefield(game, player, LeylineAxe())
    creatures = [
        put_on_battlefield(game, player, Creature(name=f"Bear {i}", base_power=2, base_toughness=2))
        for i in range(count)
    ]
    player.mana_pool.add(ManaType.COLORLESS, mana)
    return game, player, axe, creatures


def equip(game, player, axe, target):
    prefer(player, object_preference(game, target))
    activate_card_ability(game, player, axe)
    resolve_stack(game)


def test_static_data():
    card = LeylineAxe()
    assert printed_class(card) is LeylineAxe and card.mana_cost == ManaCost.parse("{4}")
    assert card.equip_cost == ManaCost.parse("{3}")


def test_is_equipment():
    card = LeylineAxe()
    assert isinstance(card, Equipment) and card.is_equipment
    assert "Equipment" in card.subtypes


def test_equip_buffs_then_equipment_departure_removes_buff():
    game, player, axe, (bear,) = arrange()
    equip(game, player, axe, bear)
    assert axe.attached_to is bear and (bear.power, bear.toughness) == (3, 3)
    assert bear.keywords & Keyword.DOUBLE_STRIKE and bear.keywords & Keyword.TRAMPLE
    move_to_zone(game, axe, Zone.BATTLEFIELD, Zone.HAND)
    assert axe.attached_to is None and (bear.power, bear.toughness) == (2, 2)
    assert not bear.keywords & Keyword.DOUBLE_STRIKE


def test_buff_moves_when_re_equipped():
    game, player, axe, (first, second) = arrange(2, 6)
    equip(game, player, axe, first)
    assert (first.power, second.power) == (3, 2)
    equip(game, player, axe, second)
    assert (first.power, second.power) == (2, 3) and player.mana_pool.total() == 0


def test_creature_death_detaches_equipment():
    game, player, axe, (bear,) = arrange()
    equip(game, player, axe, bear)
    destroy(game, bear)
    resolve_stack(game)
    from engine.stack import settle_after_resolution

    settle_after_resolution(game)
    assert axe.attached_to is None and game.get_graveyard(player).contains(bear)


def test_equip_only_at_sorcery_speed():
    game, player, axe, (bear,) = arrange()
    game.phase = Phase.COMBAT
    prefer(player, object_preference(game, bear))
    with pytest.raises(AbilityError):
        activate_card_ability(game, player, axe)
    assert player.mana_pool.total() == 3 and axe.attached_to is None


def test_equip_no_legal_target_spends_no_mana():
    game, player, axe, _ = arrange(0)
    put_on_battlefield(
        game, game.players[1], Creature(name="Theirs", base_power=2, base_toughness=2)
    )
    with pytest.raises(AbilityError):
        activate_card_ability(game, player, axe)
    assert player.mana_pool.total() == 3 and axe.attached_to is None and game.stack.is_empty()


def test_equip_pays_before_attachment_resolves():
    game, player, axe, (bear,) = arrange()
    prefer(player, object_preference(game, bear))
    activate_card_ability(game, player, axe)
    assert player.mana_pool.total() == 0 and axe.attached_to is None
    resolve_stack(game)
    assert axe.attached_to is bear and bear.power == 3
