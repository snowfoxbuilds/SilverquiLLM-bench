"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state, _resolve_top_of_stack


class SmallInstant(Instant):
    def __init__(self, mv=1, name="SmallInstant", **kwargs):
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost(generic=mv))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


class SmallCreature(Creature):
    def __init__(self, mv=2, name="SmallCreature", **kwargs):
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost(generic=mv))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def _advance_to_next_precombat_main(game, target_player):
    orig_turn = game.turn_number
    from engine.game_state import _TURN_SEQUENCE
    for _ in range(len(_TURN_SEQUENCE) * 3):
        game.advance_phase()
        if (game.phase == Phase.PRECOMBAT_MAIN and
                game.active_player is target_player and
                game.turn_number > orig_turn):
            return


def test_exiles_until_mv_4():
    """Capstone exiles cards until total MV >= 4."""
    game = create_game()
    p1 = game.players[0]

    # Library: 4 cards each MV 1 (total MV 4 after 4 cards)
    lib_cards = [SmallInstant(mv=1, name=f"Instant{i}") for i in range(5)]
    for c in lib_cards:
        c.owner = p1
        c.controller = p1
        game.get_library(p1).add(c)

    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.RED, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 5)

    from engine.player import DeterministicPlayer
    # Decline to cast any exiled cards, and decline paradigm copy
    if isinstance(p1, DeterministicPlayer):
        for _ in range(6):
            p1._script.appendleft(False)

    cast_spell(game, 0, "Improvisation Capstone")

    # At least 4 cards should be in exile (until MV >= 4)
    exile = game.get_exile(p1).get_all()
    assert len(exile) >= 4


def test_paradigm_exiles_capstone():
    """After resolving, Capstone goes to exile (not graveyard)."""
    game = create_game()
    p1 = game.players[0]

    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.RED, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 5)

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        for _ in range(10):
            p1._script.appendleft(False)

    cast_spell(game, 0, "Improvisation Capstone")

    # Capstone should be in exile (Paradigm)
    assert capstone in game.get_exile(p1).get_all()
    assert capstone not in game.get_graveyard(p1).get_all()


def test_paradigm_offers_copy_at_next_main():
    """At beginning of each subsequent first main phase, player may cast a copy from exile."""
    game = create_game()
    p1 = game.players[0]

    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.RED, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 5)

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        for _ in range(10):
            p1._script.appendleft(False)  # decline all casts/copies initially

    cast_spell(game, 0, "Improvisation Capstone")

    # Advance to next main phase for p1
    _advance_to_next_precombat_main(game, p1)

    # The trigger fires — stack should have the Paradigm trigger
    assert not game.stack.is_empty()


def test_cast_exiled_spell_for_free():
    """Player can cast exiled instant for free during resolve."""
    game = create_game()
    p1 = game.players[0]

    instant = SmallInstant(mv=4, name="BigInstant")
    instant.owner = p1
    instant.controller = p1
    game.get_library(p1).add(instant)

    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 0
    p1.mana_pool.add(ManaType.RED, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 5)

    from engine.player import DeterministicPlayer
    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(False)   # decline paradigm copy (if any)
        p1._script.appendleft(True)    # yes, cast the instant

    cast_spell(game, 0, "Improvisation Capstone")
    _resolve_top_of_stack(game)

    # BigInstant should have been cast (not in exile anymore — in graveyard or stack)
    exile = game.get_exile(p1).get_all()
    assert instant not in exile or instant in game.get_graveyard(p1).get_all()
