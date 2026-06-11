"""Tests for The Dawning Archaic (sos_1)."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import (
    advance_to_phase,
    create_game,
    declare_attackers,
    set_board_state,
    _resolve_top_of_stack,
)


class SimpleInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "SimpleInstant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


class SimpleSorcery(Sorcery):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "SimpleSorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def test_cost_reduction_counts_instants_sorceries():
    """Costs {1} less per instant/sorcery in graveyard."""
    archaic = TheDawningArchaic()
    game = create_game()
    p1 = game.players[0]
    set_board_state(game, 0, graveyard=[SimpleInstant(), SimpleInstant(), SimpleSorcery()])
    archaic.controller = p1
    assert archaic.cost_reduction(game) == 3


def test_cost_reduction_zero_empty_graveyard():
    """No reduction when graveyard is empty."""
    archaic = TheDawningArchaic()
    game = create_game()
    p1 = game.players[0]
    archaic.controller = p1
    assert archaic.cost_reduction(game) == 0


def test_reach_keyword():
    """Archaic has Reach."""
    from engine.types import Keyword
    archaic = TheDawningArchaic()
    assert Keyword.REACH in archaic.keywords


def _setup_attack(graveyard_card=None):
    """Return (game, archaic, p1) with archaic on battlefield, triggers registered."""
    archaic = TheDawningArchaic()
    archaic.summoning_sick = False

    game = create_game()
    p1 = game.players[0]

    bf_cards = [archaic]
    gy_cards = [graveyard_card] if graveyard_card else []
    set_board_state(game, 0, battlefield=bf_cards, graveyard=gy_cards)
    archaic.register_triggers(game)
    return game, archaic, p1


def test_attack_trigger_casts_from_graveyard():
    """Attacking fires trigger; card from graveyard is cast free."""
    target_instant = SimpleInstant()
    game, archaic, p1 = _setup_attack(target_instant)

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(target_instant)

    declare_attackers(game, ["The Dawning Archaic"])
    _resolve_top_of_stack(game)

    # The instant should have been cast and left the graveyard
    gy_cards = game.get_graveyard(p1).get_all()
    assert target_instant not in gy_cards


def test_spell_exiled_instead_of_graveyard():
    """After being cast from graveyard via Archaic, spell goes to exile not graveyard."""
    target_instant = SimpleInstant()
    game, archaic, p1 = _setup_attack(target_instant)

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(target_instant)

    declare_attackers(game, ["The Dawning Archaic"])
    _resolve_top_of_stack(game)

    # Should be in exile, not graveyard
    assert target_instant not in game.get_graveyard(p1).get_all()
    assert target_instant in game.get_exile(p1).get_all()


def test_no_trigger_when_graveyard_empty():
    """With empty graveyard, attack trigger does nothing gracefully."""
    game, archaic, p1 = _setup_attack()

    declare_attackers(game, ["The Dawning Archaic"])
    _resolve_top_of_stack(game)  # should not raise
