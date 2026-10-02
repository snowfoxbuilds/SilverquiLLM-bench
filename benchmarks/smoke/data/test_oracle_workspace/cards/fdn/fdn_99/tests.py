"""Reference test for FDN 99 — Apothecary Stomper.

Exemplar for a **modal ETB creature** (Phase D, Pattern 5 + Pattern 1). The mode
is chosen at cast in ``get_targets`` (answered by a MODE Intent) and stored on
``chosen_mode``; mode 0 ("Put two +1/+1 counters on target creature you control")
returns a creature-target requirement, mode 1 ("You gain 4 life") is
non-targeted. The effect resolves in ``on_resolve`` before the Stomper arrives.
"""

from __future__ import annotations

from cards.fdn.fdn_99.card_impl import ApothecaryStomper
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import resolve_top_of_stack
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _cast_no_resolve_mode(game, player_index, card, mode_name, targets):
    """Cast a modal *card* choosing *mode_name*, leaving it on the stack."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = (Decision.mode(mode_name),) + tuple(
        Decision.obj(instance=game.refs.instance_id(t, Zone.BATTLEFIELD.value))
        for t in targets
    )
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("name", card.name)})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


def _specs_for_mode(game, player, card, mode_name):
    player.start_intent(
        "mode",
        Intent(
            pattern=GameRef(card=frozenset({("name", card.name)})),
            preferences=(Decision.mode(mode_name),),
        ),
    )
    try:
        return card.get_targets(game)
    finally:
        player.end_intent("mode")


def _cast_mode(game, player_index, player, card_name, mode_name):
    player.start_intent(
        "mode",
        Intent(
            pattern=GameRef(card=frozenset({("name", card_name)})),
            preferences=(Decision.mode(mode_name),),
        ),
    )
    try:
        cast_spell(game, player_index, card_name)
    finally:
        player.end_intent("mode")


class TestApothecaryStomperProperties:
    def test_static_data(self):
        card = ApothecaryStomper(owner=None)
        assert card.name == "Apothecary Stomper"
        assert card.mana_cost == ManaCost.parse("{4}{G}{G}")
        assert (card.base_power, card.base_toughness) == (4, 4)
        assert card.subtypes == {"Elephant"}
        assert Keyword.VIGILANCE & card.keywords
        assert [m.name for m in card.get_modes()] == ["Counters", "Life"]


class TestApothecaryStomperModes:
    def test_mode0_puts_two_counters_on_your_creature(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        mine = _bear("My Bear")
        set_board_state(game, 0, hand=[stomper], battlefield=[mine],
                        mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4})
        game.phase = Phase.PRECOMBAT_MAIN

        # First offered mode is Counters (mode 0); target the friendly creature.
        cast_spell(game, 0, "Apothecary Stomper", targets=[mine])
        assert stomper.chosen_mode == 0
        assert mine.plus_one_counters == 2
        assert (mine.power, mine.toughness) == (4, 4)
        assert game.get_battlefield(p1).contains(stomper)

    def test_mode1_gains_four_life(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[stomper], life=20,
                        mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4})
        game.phase = Phase.PRECOMBAT_MAIN

        _cast_mode(game, 0, p1, "Apothecary Stomper", "Life")
        assert stomper.chosen_mode == 1
        assert p1.life == 24
        assert game.get_battlefield(p1).contains(stomper)

    def test_option_set_mode0_targets_only_creatures_you_control(self):
        """Legality invariant: mode 0 accepts a creature you control and rejects
        an opponent's creature; mode 1 requests no target."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        mine = _bear("My Bear")
        theirs = _bear("Their Bear")
        set_board_state(game, 0, battlefield=[stomper, mine])
        set_board_state(game, 1, battlefield=[theirs])

        mode0 = _specs_for_mode(game, p1, stomper, "Counters")
        assert stomper.chosen_mode == 0
        assert len(mode0) == 1
        spec = mode0[0]
        assert spec.filter_fn(mine) is True
        assert spec.filter_fn(theirs) is False

        mode1 = _specs_for_mode(game, p1, stomper, "Life")
        assert stomper.chosen_mode == 1
        assert mode1 == []


class TestApothecaryStomperRevalidation:
    """Rule 608.2b: mode 0 revalidates the FULL predicate ("a creature you
    control") at resolution, not merely control + presence."""

    def test_mode0_no_counters_when_target_not_a_creature(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        stomper = ApothecaryStomper(owner=p1, controller=p1)
        mine = _bear("My Bear")
        set_board_state(game, 0, hand=[stomper], battlefield=[mine],
                        mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4})
        game.phase = Phase.PRECOMBAT_MAIN

        _cast_no_resolve_mode(game, 0, stomper, "Counters", [mine])
        # Before resolution the chosen target loses creature-ness.
        mine.card_types = set(mine.card_types) - {CardType.CREATURE}
        while not game.stack.is_empty():
            resolve_top_of_stack(game)

        assert stomper.chosen_mode == 0
        # No counters were placed.
        assert mine.plus_one_counters == 0
        # The Stomper itself still entered the battlefield.
        assert game.get_battlefield(p1).contains(stomper)
