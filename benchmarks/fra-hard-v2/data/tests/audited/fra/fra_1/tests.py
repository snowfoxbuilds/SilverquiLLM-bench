import pytest
from card_impl import EmrakulTheExigentDoom, EmrakulTheExigentDoomAbility5
from engine.basic_lands import Forest, ForestAbility1
from engine.card import ActivatedAbility, Artifact, Creature, Instant
from engine.casting import resolve_top
from engine.decisions import Decision
from engine.game import exile
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, TargetRequirement, Zone
from engine.zones import move_to_zone
from test_utils import (
    act,
    act_illegal,
    activate_card_ability,
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    enter_permanent,
    object_preference,
    prefer,
    resolve_stack,
    take_action,
)


def arrange():
    game = behavioral_game()
    player = game.players[0]
    emrakul = EmrakulTheExigentDoom(owner=player)
    game.get_hand(player).add(emrakul)
    land = enter_permanent(game, player, Forest())
    player.mana_pool.add(ManaType.COLORLESS, 3)
    prefer(player, object_preference(game, land))
    return game, player, emrakul, land


def exile_ability(game, emrakul):
    take_action(game, 0, act(EmrakulTheExigentDoomAbility5))
    resolve_stack(game)


def granted_mana(game, land):
    """The "{T}: Add {C}{C}" ``land`` gains, by its source and printed identity."""
    instance = dict(object_preference(game, land).attrs)["instance"]
    return Decision.ability(source=instance, printed=EmrakulTheExigentDoomAbility5)


def tap_for_granted_mana(game, seat=0):
    take_action(game, seat, act(Decision.ability(printed=EmrakulTheExigentDoomAbility5)))


def assert_grant(game, land, seat=0):
    """The untapped ``land`` taps for {C}{C} through the granted ability."""
    pool = game.players[seat].mana_pool
    before = pool.total()
    take_action(game, seat, act(granted_mana(game, land)))
    assert land.is_tapped and pool.total() == before + 2


def assert_no_grant(game, land, seat=0):
    """The untapped ``land`` has no granted ability that can take effect."""
    pool = game.players[seat].mana_pool
    before = pool.total()
    take_action(game, seat, act_illegal(granted_mana(game, land)))
    assert not land.is_tapped and pool.total() == before


def test_exile_is_cost_and_land_grant_waits_for_resolution():
    game, player, emrakul, land = arrange()
    take_action(game, 0, act(EmrakulTheExigentDoomAbility5))
    assert player.zones[Zone.EXILE].contains(emrakul) and player.mana_pool.total() == 0
    assert_no_grant(game, land)
    resolve_stack(game)
    assert_grant(game, land)
    assert player.mana_pool.total() == 2


def test_grant_is_additional_not_replacement():
    game, player, emrakul, land = arrange()
    exile_ability(game, emrakul)
    take_action(game, 0, act(ForestAbility1))
    assert player.mana_pool.can_pay(ManaCost.parse("{G}"))


def test_cast_from_exile_ends_grant_and_untaps_lands():
    game, player, emrakul, land = arrange()
    exile_ability(game, emrakul)
    land.is_tapped = True
    player.mana_pool.add(ManaType.COLORLESS, 10)
    take_action(game, 0, act(EmrakulTheExigentDoom))
    assert land.is_tapped
    resolve_top(game)
    assert not land.is_tapped and not game.get_battlefield(player).contains(emrakul)
    resolve_stack(game)
    assert game.get_battlefield(player).contains(emrakul)
    assert_no_grant(game, land)
    assert emrakul.power == 12 and emrakul.toughness == 12
    assert Keyword.FLYING in emrakul.keywords and Keyword.TRAMPLE in emrakul.keywords


def test_granted_mana_can_pay_for_emrakul_before_it_expires():
    game, player, emrakul, land = arrange()
    exile_ability(game, emrakul)
    player.mana_pool.add(ManaType.COLORLESS, 8)
    tap_for_granted_mana(game)
    assert land.is_tapped and player.mana_pool.total() == 10
    take_action(game, 0, act(EmrakulTheExigentDoom))
    resolve_stack(game)
    assert game.get_battlefield(player).contains(emrakul) and player.mana_pool.total() == 0
    assert not land.is_tapped
    assert_no_grant(game, land)


def test_grant_survives_cleanup():
    game, _player, emrakul, land = arrange()
    exile_ability(game, emrakul)
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert_grant(game, land)


def test_exile_cast_requires_normal_timing_and_mana():
    game, player, emrakul, _land = arrange()
    exile_ability(game, emrakul)
    take_action(game, 0, act_illegal(EmrakulTheExigentDoom))
    player.mana_pool.add(ManaType.COLORLESS, 10)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    take_action(game, 0, act_illegal(EmrakulTheExigentDoom))
    assert player.zones[Zone.EXILE].contains(emrakul)


def test_land_removed_in_response_fizzles_and_no_cast_permission():
    game, player, emrakul, land = arrange()
    take_action(game, 0, act(EmrakulTheExigentDoomAbility5))
    exile(game, land)
    resolve_stack(game)
    player.mana_pool.add(ManaType.COLORLESS, 10)
    take_action(game, 0, act_illegal(EmrakulTheExigentDoom))
    assert player.zones[Zone.EXILE].contains(emrakul)


def test_land_blink_removes_granted_ability():
    game, _player, emrakul, land = arrange()
    exile_ability(game, emrakul)
    move_to_zone(game, land, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, land, Zone.EXILE, Zone.BATTLEFIELD)
    assert_no_grant(game, land)


def test_emrakul_leaving_exile_other_way_does_not_expire_land_grant():
    game, player, emrakul, land = arrange()
    exile_ability(game, emrakul)
    move_to_zone(game, emrakul, Zone.EXILE, Zone.HAND)
    player.mana_pool.add(ManaType.COLORLESS, 10)
    take_action(game, 0, act(EmrakulTheExigentDoom))
    resolve_stack(game)
    assert game.get_battlefield(player).contains(emrakul)
    assert_grant(game, land)


def test_exile_permission_does_not_follow_return_to_exile():
    game, player, emrakul, _land = arrange()
    exile_ability(game, emrakul)
    move_to_zone(game, emrakul, Zone.EXILE, Zone.HAND)
    move_to_zone(game, emrakul, Zone.HAND, Zone.EXILE)
    player.mana_pool.add(ManaType.COLORLESS, 10)
    take_action(game, 0, act_illegal(EmrakulTheExigentDoom))
    assert player.zones[Zone.EXILE].contains(emrakul)


def test_noncast_entry_does_not_untap_lands():
    game, _player, emrakul, land = arrange()
    land.is_tapped = True
    move_to_zone(game, emrakul, Zone.HAND, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert land.is_tapped


def test_cast_untaps_only_your_lands():
    game, player, _emrakul, land = arrange()
    enemy = enter_permanent(game, game.players[1], Forest())
    artifact = enter_permanent(game, player, Artifact(name="Relic"))
    land.is_tapped = enemy.is_tapped = artifact.is_tapped = True
    player.mana_pool.add(ManaType.COLORLESS, 7)
    take_action(game, 0, act(EmrakulTheExigentDoom))
    resolve_top(game)
    assert not land.is_tapped and enemy.is_tapped and artifact.is_tapped


class Removal(Instant):
    def __init__(self, **kwargs):
        super().__init__(name="Removal", mana_cost=ManaCost(), **kwargs)

    def get_targets(self, game):
        return [TargetRequirement(lambda card: CardType.CREATURE in getattr(card, "card_types", set()),
                                  "Target creature", Zone.BATTLEFIELD)]

    def on_resolve(self, game):
        exile(game, self.chosen_targets[0])


@pytest.mark.parametrize("permanents", [0, 2, 3])
def test_ward_requires_three_permanents(permanents):
    game, player, emrakul, _land = arrange()
    move_to_zone(game, emrakul, Zone.HAND, Zone.BATTLEFIELD)
    opponent = game.players[1]
    for _ in range(permanents):
        enter_permanent(game, opponent, Forest())
    prefer(opponent, object_preference(game, emrakul), Decision.yes())
    spell = Removal(owner=opponent)
    cast_card(game, opponent, spell)
    if permanents < 3:
        assert game.get_battlefield(player).contains(emrakul)
        assert opponent.zones[Zone.GRAVEYARD].contains(spell)
        assert len(game.get_battlefield(opponent).get_all()) == permanents
    else:
        assert player.zones[Zone.EXILE].contains(emrakul)
        assert len(game.get_battlefield(opponent).get_all()) == 0


def test_ward_can_be_declined_even_with_payment_available():
    game, player, emrakul, _land = arrange()
    move_to_zone(game, emrakul, Zone.HAND, Zone.BATTLEFIELD)
    opponent = game.players[1]
    for _ in range(3):
        enter_permanent(game, opponent, Forest())
    prefer(opponent, object_preference(game, emrakul), Decision.no())
    cast_card(game, opponent, Removal(owner=opponent))
    assert game.get_battlefield(player).contains(emrakul)
    assert len(game.get_battlefield(opponent).get_all()) == 3


def test_your_own_targeting_does_not_trigger_ward():
    game, player, emrakul, land = arrange()
    move_to_zone(game, emrakul, Zone.HAND, Zone.BATTLEFIELD)
    prefer(player, object_preference(game, emrakul))
    cast_card(game, player, Removal(owner=player))
    assert player.zones[Zone.EXILE].contains(emrakul) and game.get_battlefield(player).contains(land)


class Exiler(Creature):
    def __init__(self, target, **kwargs):
        super().__init__(name="Exiler", base_power=1, base_toughness=1, **kwargs)
        self.target = target

    def get_activated_abilities(self):
        return [ActivatedAbility(lambda g, s: True,
            lambda g, targets, context: exile(g, targets[0]),
            targeting=lambda g, s, p: [self.target])]


def test_ward_counters_activated_ability_without_removing_source():
    game, player, emrakul, _land = arrange()
    move_to_zone(game, emrakul, Zone.HAND, Zone.BATTLEFIELD)
    opponent = game.players[1]
    source = enter_permanent(game, opponent, Exiler(emrakul))
    activate_card_ability(game, opponent, source)
    resolve_stack(game)
    assert game.get_battlefield(player).contains(emrakul)
    assert game.get_battlefield(opponent).contains(source)


def test_opponents_land_can_receive_grant_but_not_cast_permission():
    game, player, emrakul, _ = arrange()
    opponent = game.players[1]
    land = enter_permanent(game, opponent, Forest())
    prefer(player, object_preference(game, land))
    exile_ability(game, emrakul)
    tap_for_granted_mana(game, seat=1)
    assert opponent.mana_pool.total() == 2
    opponent.mana_pool.add(ManaType.COLORLESS, 10)
    game.active_player_index = 1
    take_action(game, 1, act_illegal(EmrakulTheExigentDoom))
    assert player.zones[Zone.EXILE].contains(emrakul)


def test_insufficient_activation_mana_does_not_exile_or_pay():
    game, player, emrakul, _ = arrange()
    player.mana_pool.pay(ManaCost(generic=1))
    take_action(game, 0, act_illegal(EmrakulTheExigentDoomAbility5))
    assert game.get_hand(player).contains(emrakul)
    assert player.mana_pool.total() == 2


def test_exile_activation_is_not_available_on_battlefield():
    game, player, emrakul, _ = arrange()
    move_to_zone(game, emrakul, Zone.HAND, Zone.BATTLEFIELD)
    take_action(game, 0, act_illegal(EmrakulTheExigentDoomAbility5))
    assert game.get_battlefield(player).contains(emrakul)
    assert player.mana_pool.total() == 3


def test_land_grant_resolves_even_if_emrakul_already_left_exile():
    game, player, emrakul, land = arrange()
    take_action(game, 0, act(EmrakulTheExigentDoomAbility5))
    move_to_zone(game, emrakul, Zone.EXILE, Zone.HAND)
    resolve_stack(game)
    assert_grant(game, land)
    assert game.get_hand(player).contains(emrakul)


def test_blinked_land_in_response_gets_no_grant_or_permission():
    game, player, emrakul, land = arrange()
    take_action(game, 0, act(EmrakulTheExigentDoomAbility5))
    move_to_zone(game, land, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, land, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert_no_grant(game, land)
    player.mana_pool.add(ManaType.COLORLESS, 10)
    take_action(game, 0, act_illegal(EmrakulTheExigentDoom))
    assert player.zones[Zone.EXILE].contains(emrakul)


def test_countering_emrakul_does_not_counter_its_cast_trigger():
    from cards.fdn.fdn_153.card_impl import EssenceScatter

    game, player, emrakul, land = arrange()
    land.is_tapped = True
    player.mana_pool.add(ManaType.COLORLESS, 7)
    take_action(game, 0, act(EmrakulTheExigentDoom))
    opponent = game.players[1]
    opponent.mana_pool.add(ManaType.BLUE, 1)
    opponent.mana_pool.add(ManaType.COLORLESS, 1)
    cast_card(game, opponent, EssenceScatter(), resolve=False)
    resolve_top(game)
    assert player.zones[Zone.GRAVEYARD].contains(emrakul) and land.is_tapped
    resolve_stack(game)
    assert not land.is_tapped
