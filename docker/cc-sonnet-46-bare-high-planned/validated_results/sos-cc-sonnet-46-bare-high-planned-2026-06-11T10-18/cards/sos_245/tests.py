"""Tests for Witherbloom, the Balancer (sos_245)."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Phase
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


class BearCreature(Creature):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Bear")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class TestInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "TestInstant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def test_flying_deathtouch():
    """Witherbloom has Flying and Deathtouch."""
    wb = WitherbloomTheBalancer()
    assert Keyword.FLYING in wb.keywords
    assert Keyword.DEATHTOUCH in wb.keywords


def test_own_cost_reduction_no_creatures():
    """Affinity: 0 reduction when controlling no creatures."""
    wb = WitherbloomTheBalancer()
    game = create_game()
    p1 = game.players[0]
    wb.controller = p1
    assert wb.cost_reduction(game) == 0


def test_own_cost_reduction_with_creatures():
    """Affinity: costs {1} less per creature controlled."""
    wb = WitherbloomTheBalancer()
    game = create_game()
    p1 = game.players[0]
    bears = [BearCreature() for _ in range(3)]
    set_board_state(game, 0, battlefield=bears)
    wb.controller = p1
    assert wb.cost_reduction(game) == 3


def test_spell_cost_reduction_grants_affinity():
    """Witherbloom on battlefield reduces costs of your instant/sorcery spells."""
    wb = WitherbloomTheBalancer()
    spell = TestInstant()

    game = create_game()
    p1 = game.players[0]

    bear1 = BearCreature()
    bear2 = BearCreature()
    # Witherbloom + 2 bears on battlefield; cast a {3} instant
    set_board_state(game, 0, battlefield=[wb, bear1, bear2], hand=[spell])
    wb.controller = p1
    wb.register_triggers(game)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0

    # With 3 creatures on battlefield (wb, bear1, bear2), instant costs 3 less
    # TestInstant costs {3}, so it's free. Pay {0}.
    p1.mana_pool.add(ManaType.COLORLESS, 0)  # zero mana — E3 should make it free

    cast_spell(game, 0, "TestInstant")

    # Instant was cast (no exception) — it's no longer in hand
    assert spell not in game.get_hand(p1).get_all()


def test_spell_reduction_only_for_own_spells():
    """Witherbloom only reduces spells cast by its controller, not opponents."""
    wb = WitherbloomTheBalancer()
    spell = TestInstant()

    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    bears = [BearCreature() for _ in range(3)]
    set_board_state(game, 0, battlefield=[wb] + bears)
    wb.controller = p1

    # The spell_cost_reduction for a spell controlled by p2 should be 0
    spell.controller = p2
    assert wb.spell_cost_reduction(game, spell) == 0
