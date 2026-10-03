"""Embercleave's attacking discount, paid equip and entry attachment are observable."""

from cards.fdn.spg_77.card_impl import Embercleave
from engine.card import Creature, Equipment
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import (
    activate_card_ability,
    behavioral_game,
    cast_card,
    declare_attackers,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def test_static_data():
    card = Embercleave()
    assert card.name == "Embercleave" and card.mana_cost == ManaCost.parse("{4}{R}{R}")
    assert card.equip_cost == ManaCost.parse("{3}")
    assert Supertype.LEGENDARY in card.supertypes and card.keywords & Keyword.FLASH
    assert isinstance(card, Equipment) and card.is_equipment


def test_cost_reduction_per_attacking_creature():
    game = behavioral_game()
    player = game.players[0]
    attackers = [
        put_on_battlefield(game, player, Creature(name=f"Bear {i}", base_power=2, base_toughness=2))
        for i in range(2)
    ]
    for card in attackers:
        card.summoning_sick = False
    declare_attackers(game, [card.name for card in attackers])
    player.mana_pool.add(ManaType.RED, 2)
    player.mana_pool.add(ManaType.COLORLESS, 2)
    prefer(player, object_preference(game, attackers[0]))
    cleave = Embercleave(owner=player)
    cast_card(game, player, cleave)
    assert player.mana_pool.total() == 0 and cleave.attached_to is attackers[0]
    assert game.get_battlefield(player).contains(cleave)


def test_static_buff_after_paid_equip():
    game = behavioral_game()
    player = game.players[0]
    bear = put_on_battlefield(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    cleave = put_on_battlefield(game, player, Embercleave())
    player.mana_pool.add(ManaType.COLORLESS, 3)
    prefer(player, object_preference(game, bear))
    activate_card_ability(game, player, cleave)
    resolve_stack(game)
    assert (bear.power, bear.toughness) == (3, 3)
    assert bear.keywords & Keyword.DOUBLE_STRIKE and bear.keywords & Keyword.TRAMPLE


def test_cast_entry_attaches_to_the_chosen_creature():
    game = behavioral_game()
    player = game.players[0]
    bear = put_on_battlefield(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    other = put_on_battlefield(game, player, Creature(name="Other", base_power=2, base_toughness=2))
    player.mana_pool.add(ManaType.RED, 6)
    prefer(player, object_preference(game, bear))
    cleave = Embercleave(owner=player)
    cast_card(game, player, cleave)
    assert cleave.attached_to is bear and bear.power == 3 and other.power == 2
