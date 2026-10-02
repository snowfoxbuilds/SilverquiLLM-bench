import pytest
from card_impl import SanctumLurker
from engine.abilities import AbilityError
from engine.card import Instant, Planeswalker
from engine.game import exile, remove_counter
from engine.types import CardType, ManaCost, Phase, Step, Zone
from test_utils import (
    activate_loyalty_ability,
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    enter_permanent,
    put_on_battlefield,
    resolve_stack,
)


def arrange():
    game = behavioral_game()
    player = game.players[0]
    lurker = enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    jace = next(c for c in game.get_battlefield(player).get_all() if "Jace" in c.subtypes)
    return game, player, lurker, jace


def test_enters_creates_jace_with_one_loyalty():
    _game, _player, lurker, jace = arrange()
    assert jace.is_token and jace.loyalty == 1
    assert CardType.PLANESWALKER in jace.card_types
    assert lurker.power == 3 and lurker.toughness == 2


def test_second_empower_reuses_token():
    game, player, _, jace = arrange()
    enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    assert jace.loyalty == 2
    assert len([c for c in game.get_battlefield(player).get_all() if "Jace" in c.subtypes]) == 1


def test_granted_plus_two_drains_and_gains():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    assert jace.loyalty == 3 and game.players[1].life == 20
    resolve_stack(game)
    assert player.life == 21 and game.players[1].life == 19


def test_granted_ability_obeys_once_per_turn():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    resolve_stack(game)
    with pytest.raises(AbilityError):
        activate_loyalty_ability(game, player, jace, 0)
    assert jace.loyalty == 3


def test_granted_ability_obeys_sorcery_timing():
    game, player, _, jace = arrange()
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    with pytest.raises(AbilityError):
        activate_loyalty_ability(game, player, jace, 2)
    assert jace.loyalty == 1


def test_pending_empower_survives_lurker_leaving():
    game = behavioral_game()
    player = game.players[0]
    lurker = enter_permanent(game, player, SanctumLurker())
    exile(game, lurker)
    resolve_stack(game)
    jaces = [c for c in game.get_battlefield(player).get_all() if "Jace" in c.subtypes]
    assert len(jaces) == 1 and jaces[0].loyalty == 1


def test_zero_loyalty_protection_does_not_prevent_sacrifice():
    from engine.game import sacrifice

    game, player, lurker, jace = arrange()
    remove_counter(game, jace, "loyalty", 1)
    sacrifice(game, player, jace)
    resolve_stack(game)
    assert not game.get_battlefield(player).contains(jace)
    assert game.get_battlefield(player).contains(lurker)


def test_minus_three_draws_but_cannot_pay_insufficient_loyalty():
    game, player, _, jace = arrange()
    with pytest.raises(AbilityError):
        activate_loyalty_ability(game, player, jace, 1)
    assert jace.loyalty == 1
    from engine.game import add_counter
    add_counter(game, jace, "loyalty", 2)
    activate_loyalty_ability(game, player, jace, 1)
    resolve_stack(game)
    assert jace.loyalty == 0 and len(game.get_hand(player).get_all()) == 1


def test_pending_drain_survives_planeswalker_leaving():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    exile(game, jace)
    resolve_stack(game)
    assert player.life == 21 and game.players[1].life == 19


def test_opposing_jace_token_is_not_empowered():
    game = behavioral_game()
    player, opponent = game.players
    enter_permanent(game, opponent, SanctumLurker())
    resolve_stack(game)
    old_jace = next(c for c in game.get_battlefield(opponent).get_all() if "Jace" in c.subtypes)
    enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    new_jace = next(c for c in game.get_battlefield(player).get_all() if "Jace" in c.subtypes)
    assert old_jace is not new_jace and old_jace.loyalty == new_jace.loyalty == 1


def test_zero_loyalty_token_survives_minus_one():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 0)
    resolve_stack(game)
    assert jace.loyalty == 0 and game.get_battlefield(player).contains(jace)
    assert len(player.zones[Zone.GRAVEYARD].get_all()) == 1


def test_zero_loyalty_dies_when_lurker_leaves():
    game, player, lurker, jace = arrange()
    remove_counter(game, jace, "loyalty", 1)
    exile(game, lurker)
    resolve_stack(game)
    assert not game.get_battlefield(player).contains(jace)


def test_second_lurker_keeps_zero_loyalty_safe():
    game, player, lurker, jace = arrange()
    other = enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    remove_counter(game, jace, "loyalty", 2)
    exile(game, lurker)
    resolve_stack(game)
    assert game.get_battlefield(player).contains(jace)
    exile(game, other)
    resolve_stack(game)
    assert not game.get_battlefield(player).contains(jace)


def test_nontoken_planeswalker_also_gets_protection_and_ability():
    game, player, _, _ = arrange()
    walker = enter_permanent(game, player, Planeswalker(name="Visitor", starting_loyalty=0))
    resolve_stack(game)
    activate_loyalty_ability(game, player, walker)
    resolve_stack(game)
    assert walker.loyalty == 2 and player.life == 21


def test_opponents_planeswalker_not_protected():
    game, _player, _, _ = arrange()
    opponent = game.players[1]
    walker = put_on_battlefield(game, opponent, Planeswalker(name="Opposing walker", starting_loyalty=0))
    resolve_stack(game)
    assert opponent.zones[Zone.GRAVEYARD].contains(walker)


def test_existing_nontoken_jace_does_not_replace_token_creation():
    game = behavioral_game()
    player = game.players[0]
    walker = enter_permanent(game, player, Planeswalker(name="Jace visitor", subtypes={"Jace"}, starting_loyalty=4))
    enter_permanent(game, player, SanctumLurker())
    resolve_stack(game)
    assert walker.loyalty == 4
    assert len([c for c in game.get_battlefield(player).get_all() if CardType.PLANESWALKER in c.card_types]) == 2


def test_grant_disappears_but_pending_ability_resolves():
    game, player, lurker, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    exile(game, lurker)
    resolve_stack(game)
    assert player.life == 21
    with pytest.raises(IndexError):
        activate_loyalty_ability(game, player, jace, 2)


def test_granted_damage_uses_planeswalker_as_lifelink_source():
    from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer
    from engine.types import Keyword

    game, player, _, jace = arrange()
    game.effect_manager.add(ContinuousEffect(
        jace, Layer.ABILITY,
        apply=lambda state: setattr(jace, "keywords", jace.keywords | Keyword.LIFELINK),
        duration=DURATION_END_OF_TURN,
    ))
    game.effect_manager.apply_all(game)
    activate_loyalty_ability(game, player, jace, 2)
    resolve_stack(game)
    assert game.players[1].life == 19 and player.life == 22


class ControlChange(Instant):
    def __init__(self, target, **kwargs):
        super().__init__(name="Control change", mana_cost=ManaCost(), **kwargs)
        self.target = target

    def on_resolve(self, game):
        from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer

        controller = self.controller

        def apply(state):
            for previous in state.players:
                if state.get_battlefield(previous).contains(self.target):
                    if previous is not controller:
                        state.get_battlefield(previous).remove(self.target)
                        state.get_battlefield(controller).add(self.target)
                    self.target.controller = controller
                    break

        game.effect_manager.add(ContinuousEffect(
            self, Layer.CONTROL, apply=apply, duration=DURATION_END_OF_TURN,
        ))

def test_pending_drain_keeps_activating_controller_after_jace_is_stolen():
    game, player, _, jace = arrange()
    activate_loyalty_ability(game, player, jace, 2)
    opponent = game.players[1]
    cast_card(game, opponent, ControlChange(jace))
    assert jace.controller is opponent
    assert player.life == 21 and opponent.life == 19


def test_stealing_lurker_moves_zero_loyalty_protection_to_new_controller():
    game, player, lurker, jace = arrange()
    remove_counter(game, jace, "loyalty", 1)
    opponent = game.players[1]
    cast_card(game, opponent, ControlChange(lurker))
    assert lurker.controller is opponent
    assert not game.get_battlefield(player).contains(jace)
