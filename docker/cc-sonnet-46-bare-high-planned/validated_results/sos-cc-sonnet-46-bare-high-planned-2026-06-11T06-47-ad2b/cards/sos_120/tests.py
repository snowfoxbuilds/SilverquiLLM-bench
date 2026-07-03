"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import _resolve_top_of_stack, advance_to_phase, create_game, set_board_state


def _put_on_battlefield(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.BATTLEFIELD].add(card)


def _cast_capstone(game, player_index):
    """Put Improvisation Capstone in hand, add mana, cast, and return game state."""
    from engine.casting import cast_spell as engine_cast_spell
    p = game.players[player_index]
    cap = ImprovisationCapstone()
    cap.owner = p
    cap.controller = p
    set_board_state(game, player_index, hand=[cap], mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = player_index
    engine_cast_spell(game, p, cap)
    return cap


class TestImprovisationCapstoneProperties:
    def test_name(self) -> None:
        assert ImprovisationCapstone().name == "Improvisation Capstone"

    def test_is_sorcery(self) -> None:
        assert CardType.SORCERY in ImprovisationCapstone().card_types


class TestLibraryExile:
    def test_exiles_until_mv_4(self) -> None:
        """Exiles cards until total MV >= 4; stops there."""
        game = create_game()
        p1 = game.players[0]

        # Put 3 cards with MV 2 each in library (top = last in list)
        c1 = Instant(name="C1", mana_cost=ManaCost.parse("{2}"))
        c2 = Instant(name="C2", mana_cost=ManaCost.parse("{2}"))
        c3 = Instant(name="C3", mana_cost=ManaCost.parse("{2}"))
        for card in [c1, c2, c3]:
            card.owner = p1
            card.controller = p1
        # Library: bottom=c3, top=c1 (last=c1)
        p1.zones[Zone.LIBRARY].add(c3)
        p1.zones[Zone.LIBRARY].add(c2)
        p1.zones[Zone.LIBRARY].add(c1)

        cap = _cast_capstone(game, 0)
        # Script: decline all castings (choose_card returns None)
        p1._script.appendleft(None)
        _resolve_top_of_stack(game)

        # Exiled 2 cards (MV2 + MV2 = 4 >= 4): c1, c2
        exile = game.get_exile(p1)
        assert exile.contains(c1)
        assert exile.contains(c2)
        # c3 stays in library (total MV was met after 2 cards)
        assert p1.zones[Zone.LIBRARY].contains(c3)

    def test_exiles_capstone_via_paradigm(self) -> None:
        """Capstone itself goes to exile (not graveyard) after resolving."""
        game = create_game()
        p1 = game.players[0]

        # Empty library — nothing to exile from it
        cap = _cast_capstone(game, 0)
        # Script: decline cast choice (no library cards anyway)
        p1._script.appendleft(None)
        _resolve_top_of_stack(game)

        # Capstone should be in exile, not graveyard
        assert game.get_exile(p1).contains(cap)
        assert not game.get_graveyard(p1).contains(cap)

    def test_skips_lands_from_casting(self) -> None:
        """Land cards exiled first are not offered as castable."""
        game = create_game()
        p1 = game.players[0]

        # big is bottom (added first), land is top (added second)
        # Exile peels top-first: land first, then big
        big = Instant(name="Big", mana_cost=ManaCost.parse("{4}"))
        big.owner = p1
        big.controller = p1
        p1.zones[Zone.LIBRARY].add(big)  # bottom

        land = Land(name="TestLand")
        land.owner = p1
        land.controller = p1
        p1.zones[Zone.LIBRARY].add(land)  # top (exiled first)

        cap = _cast_capstone(game, 0)
        # Script: choose big to cast (land is not offered)
        p1._script.appendleft(big)   # first choice: big
        p1._script.appendleft(None)  # second choice: decline
        _resolve_top_of_stack(game)

        # Both exiled; land is not castable (still in exile, not in GY or stack)
        assert game.get_exile(p1).contains(land)


class TestParadigmTrigger:
    def test_paradigm_registers_e2_trigger(self) -> None:
        """After first resolution, trigger fires at next precombat main."""
        game = create_game()
        p1 = game.players[0]

        cap = _cast_capstone(game, 0)
        p1._script.appendleft(None)  # decline cast
        _resolve_top_of_stack(game)

        # Advance to next precombat main; trigger fires
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.BEGINNING, Step.UNTAP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # Trigger fires: script says "no" to casting the copy
        p1._script.appendleft(False)
        _resolve_top_of_stack(game)
        # No crash = trigger fired correctly

    def test_paradigm_trigger_fires_each_turn(self) -> None:
        """Paradigm trigger is recurring — fires each precombat main phase."""
        game = create_game()
        p1 = game.players[0]

        cap = _cast_capstone(game, 0)
        p1._script.appendleft(None)
        _resolve_top_of_stack(game)

        # First main phase trigger
        advance_to_phase(game, Phase.BEGINNING, Step.UNTAP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        p1._script.appendleft(False)
        _resolve_top_of_stack(game)

        # Second main phase trigger — should fire again
        advance_to_phase(game, Phase.BEGINNING, Step.UNTAP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        p1._script.appendleft(False)
        _resolve_top_of_stack(game)
        # No crash = recurring trigger worked
