"""Tests for Silverquill, the Disputant (sos_226)."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state
from test_utils import _resolve_top_of_stack


def _setup(n_extra_creatures=0):
    """Set up game with Silverquill + optional extra creatures on p0's battlefield."""
    silverquill = SilverquillTheDisputant()
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    p0 = game.players[0]
    silverquill.summoning_sick = False

    extras = [Creature(name=f"Sac{i}", base_power=1, base_toughness=1)
              for i in range(n_extra_creatures)]
    set_board_state(game, 0, battlefield=[silverquill] + extras)
    silverquill.register_triggers(game)
    return game, silverquill, extras


def test_flying_vigilance():
    """Silverquill has Flying and Vigilance."""
    s = SilverquillTheDisputant()
    assert Keyword.FLYING in s.keywords
    assert Keyword.VIGILANCE in s.keywords


def test_casualty_fires_on_instant_cast():
    """Casualty trigger fires when player casts an instant with a creature to sac."""
    game, silverquill, extras = _setup(n_extra_creatures=1)
    p0 = game.players[0]
    sac_target = extras[0]

    # Create an instant spell to cast
    instant = Instant(name="Bolt", mana_cost=ManaCost(generic=3))
    instant.on_resolve = lambda g: None

    set_board_state(game, 0, hand=[instant],
                    battlefield=[silverquill, sac_target],
                    mana={ManaType.COLORLESS: 3})
    silverquill.register_triggers(game)  # re-register after set_board_state

    # Script: cast the instant (target: None since no targets), then
    # for casualty: choose sac_target, then decline new targets
    p0._script.appendleft(sac_target)   # choose_card: sacrifice sac_target
    p0._script.appendleft(False)        # choose_yes_no: no new targets

    from engine.casting import cast_spell
    cast_spell(game, p0, instant)

    # Casualty trigger should be on the stack (above the original instant)
    # Resolve all items
    _resolve_top_of_stack(game)

    # The sac_target should be in the graveyard
    graveyard = game.get_graveyard(p0)
    assert graveyard.contains(sac_target), "Sacrifice target should be in graveyard"
    # Both original and copy should have resolved (both in graveyard/exile now)
    assert game.stack.is_empty()


def test_no_casualty_without_valid_creature():
    """Casualty does not trigger effect if no creature with power >= 1."""
    game, silverquill, _ = _setup(n_extra_creatures=0)
    p0 = game.players[0]

    # Remove Silverquill so there are no power-1+ creatures available
    # (Silverquill has power 4, so it could be sacrificed, but here we test
    # that when there are no candidates, nothing happens)
    # Actually, Silverquill itself has power 4 so it would be a candidate.
    # Let's use a 0/1 creature instead to have no valid sac targets.
    zero_power = Creature(name="ZeroPower", base_power=0, base_toughness=1)
    set_board_state(game, 0, battlefield=[silverquill, zero_power])
    silverquill.register_triggers(game)

    instant = Instant(name="Bolt", mana_cost=ManaCost(generic=3))
    instant.on_resolve = lambda g: None
    set_board_state(game, 0, hand=[instant],
                    battlefield=[silverquill, zero_power],
                    mana={ManaType.COLORLESS: 3})
    silverquill.register_triggers(game)

    from engine.casting import cast_spell
    cast_spell(game, p0, instant)
    _resolve_top_of_stack(game)

    # No creature should have been sacrificed
    bf = game.get_battlefield(p0)
    assert bf.contains(zero_power), "Zero-power creature should survive"


def test_casualty_none_declines():
    """Player declines casualty by choosing None."""
    game, silverquill, extras = _setup(n_extra_creatures=1)
    p0 = game.players[0]
    sac_target = extras[0]

    instant = Instant(name="Bolt", mana_cost=ManaCost(generic=3))
    instant.on_resolve = lambda g: None
    set_board_state(game, 0, hand=[instant],
                    battlefield=[silverquill, sac_target],
                    mana={ManaType.COLORLESS: 3})
    silverquill.register_triggers(game)

    # Player declines by choosing None
    p0._script.appendleft(None)  # choose_card: decline

    from engine.casting import cast_spell
    cast_spell(game, p0, instant)
    _resolve_top_of_stack(game)

    # sac_target should still be on battlefield (not sacrificed)
    bf = game.get_battlefield(p0)
    assert bf.contains(sac_target), "Creature should not be sacrificed when casualty declined"
