import pytest
from card_impl import HallofEchoes
from engine.abilities import AbilityError
from engine.card import ActivatedAbility, Creature
from engine.game import add_counter, exile
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    advance_game_to_phase,
    behavioral_game,
    enter_permanent,
    object_preference,
    prefer,
    resolve_stack,
)


class EchoCreature(Creature):
    def __init__(self, **kwargs):
        super().__init__(name="Echo creature", mana_cost=ManaCost(generic=2),
                         base_power=3, base_toughness=4, keywords=Keyword.FLYING, **kwargs)

    def get_activated_abilities(self):
        return [ActivatedAbility(lambda g, s: True,
            lambda g: add_counter(g, self, "+1/+1", 1), "Grow")]


def arrange():
    game = behavioral_game()
    player = game.players[0]
    hall = enter_permanent(game, player, HallofEchoes())
    target = enter_permanent(game, player, EchoCreature())
    prefer(player, object_preference(game, target))
    player.mana_pool.add(ManaType.COLORLESS, 5)
    return game, player, hall, target


def test_mana_ability_adds_colorless_without_stack():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall, 1)
    assert hall.is_tapped and player.mana_pool.total() == 6 and not len(game.stack)


def test_copy_has_characteristics_and_abilities():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.name == target.name and hall.power == 3 and hall.toughness == 4
    assert CardType.LAND not in hall.card_types and Keyword.FLYING in hall.keywords
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.power == 4 and target.power == 3


def test_copy_does_not_copy_counters_or_damage_or_tapped_state():
    game, player, hall, target = arrange()
    add_counter(game, target, "+1/+1", 3)
    target.damage_marked = 2
    target.is_tapped = True
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.power == 3 and hall.damage_marked == 0 and not hall.is_tapped


def test_copy_preserves_own_tapped_state_and_counters():
    game, player, hall, _ = arrange()
    hall.is_tapped = True
    add_counter(game, hall, "charge", 2)
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.is_tapped and hall.counters.get("charge") == 2


def test_copy_expires_at_cleanup_and_land_works_again():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert hall.name == "Hall of Echoes" and hall.card_types == {CardType.LAND}
    activate_card_ability(game, player, hall, 1)
    assert player.mana_pool.total() == 1


def test_copy_target_leaves_before_resolution_fizzles():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    exile(game, target)
    resolve_stack(game)
    assert hall.card_types == {CardType.LAND}


def test_blinked_target_is_new_object():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, target, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert hall.name == "Hall of Echoes"


def test_hall_leaving_does_not_stop_legend_rule_suppression():
    game, player, hall, _target = arrange()
    activate_card_ability(game, player, hall)
    exile(game, hall)
    resolve_stack(game)
    one = enter_permanent(game, player, Creature(name="Twin", supertypes={Supertype.LEGENDARY}, base_power=2, base_toughness=2))
    two = enter_permanent(game, player, Creature(name="Twin", supertypes={Supertype.LEGENDARY}, base_power=2, base_toughness=2))
    resolve_stack(game)
    assert game.get_battlefield(player).contains(one) and game.get_battlefield(player).contains(two)
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    resolve_stack(game)
    assert len([c for c in game.get_battlefield(player).get_all() if c.name == "Twin"]) == 1


def test_legendary_copy_and_original_survive_this_turn():
    game, player, hall, target = arrange()
    target.supertypes = {Supertype.LEGENDARY}
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert game.get_battlefield(player).contains(hall) and game.get_battlefield(player).contains(target)


def test_copied_hall_leaves_as_its_printed_card():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    move_to_zone(game, hall, Zone.BATTLEFIELD, Zone.HAND)
    assert hall.name == "Hall of Echoes" and hall.card_types == {CardType.LAND}


def test_cannot_activate_without_five_mana():
    game, player, hall, _ = arrange()
    player.mana_pool.pay(ManaCost(generic=1))
    with pytest.raises(AbilityError):
        activate_card_ability(game, player, hall)
    assert player.mana_pool.total() == 4 and hall.name == "Hall of Echoes"


def test_opponents_creature_is_not_a_legal_target():
    game, player, hall, target = arrange()
    exile(game, target)
    enter_permanent(game, game.players[1], EchoCreature())
    with pytest.raises(AbilityError):
        activate_card_ability(game, player, hall)
    assert player.mana_pool.total() == 5


def test_old_land_can_attack_after_becoming_a_creature():
    from engine.combat import declare_attackers_step

    game, player, hall, _ = arrange()
    advance_game_to_phase(game, Phase.BEGINNING, Step.UNTAP)
    advance_game_to_phase(game, Phase.PRECOMBAT_MAIN)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UNTAP)
    advance_game_to_phase(game, Phase.PRECOMBAT_MAIN)
    player.mana_pool.add(ManaType.COLORLESS, 5)
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    declare_attackers_step(game, [hall])
    assert hall.is_attacking


def test_copy_of_copy_uses_copiable_values_and_expires_independently():
    game, player, hall, target = arrange()
    second = enter_permanent(game, player, HallofEchoes())
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    add_counter(game, hall, "+1/+1", 3)
    prefer(player, object_preference(game, hall))
    player.mana_pool.add(ManaType.COLORLESS, 5)
    activate_card_ability(game, player, second)
    resolve_stack(game)
    assert second.name == target.name and second.power == 3 and hall.power == 6
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert hall.name == second.name == "Hall of Echoes"


def test_plus_one_counter_on_land_applies_while_copied_and_persists():
    game, player, hall, _ = arrange()
    add_counter(game, hall, "+1/+1", 2)
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.power == 5 and hall.toughness == 6
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert hall.counters.get("+1/+1") == 2
