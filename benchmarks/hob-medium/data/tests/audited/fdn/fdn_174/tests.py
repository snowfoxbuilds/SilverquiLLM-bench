"""Fake Your Own Death resolves, returns a dying creature and expires at cleanup."""

from cards.fdn.fdn_174.card_impl import FakeYourOwnDeath
from engine.card import Creature, Instant
from engine.game import destroy, exile
from engine.types import ManaCost, ManaType, Phase, Step
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def arrange(resolve=True):
    game = behavioral_game()
    player = game.players[0]
    target = put_on_battlefield(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    spell = FakeYourOwnDeath(owner=player)
    player.mana_pool.add(ManaType.BLACK, 1)
    player.mana_pool.add(ManaType.COLORLESS, 1)
    prefer(player, object_preference(game, target))
    cast_card(game, player, spell, resolve=resolve)
    return game, player, spell, target


def test_is_instant():
    assert isinstance(FakeYourOwnDeath(), Instant)


def test_mana_cost():
    assert FakeYourOwnDeath().mana_cost == ManaCost.parse("{1}{B}")


def test_resolution_applies_buff_and_leaves_stack():
    game, player, spell, target = arrange()
    assert game.stack.is_empty() and game.get_graveyard(player).contains(spell)
    assert (target.power, target.toughness) == (4, 2)
    assert player.mana_pool.total() == 0


def test_death_returns_tapped_and_creates_treasure():
    game, player, _spell, target = arrange()
    destroy(game, target)
    resolve_stack(game)
    assert game.get_battlefield(player).contains(target) and target.is_tapped
    tokens = [c for c in game.get_battlefield(player).get_all() if getattr(c, "is_token", False)]
    assert len(tokens) == 1 and "Treasure" in tokens[0].subtypes


def test_departed_target_fizzles_without_buff_or_treasure():
    game, player, spell, target = arrange(resolve=False)
    exile(game, target)
    resolve_stack(game)
    assert game.get_exile(player).contains(target)
    assert target.power == 2 and game.get_graveyard(player).contains(spell)
    assert not any(getattr(c, "is_token", False) for c in game.get_battlefield(player).get_all())


def test_cleanup_removes_buff_and_death_return():
    game, player, _spell, target = arrange()
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    resolve_stack(game)
    assert target.power == 2
    destroy(game, target)
    resolve_stack(game)
    assert game.get_graveyard(player).contains(target)
    assert not any(getattr(c, "is_token", False) for c in game.get_battlefield(player).get_all())
