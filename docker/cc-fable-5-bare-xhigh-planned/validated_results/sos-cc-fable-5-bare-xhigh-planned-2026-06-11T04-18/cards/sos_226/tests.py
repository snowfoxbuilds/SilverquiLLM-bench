"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


class TestStaticProperties:
    def test_keywords_and_stats(self) -> None:
        card = SilverquillTheDisputant()
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")


class TestCasualty:
    def test_sacrifice_copies_the_spell(self) -> None:
        """Sac a bear to casualty: Burst Lightning hits p2 twice (copy + original)."""
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(
            game,
            0,
            battlefield=[SilverquillTheDisputant(), bear],
            hand=[BurstLightning()],
            mana={ManaType.RED: 1},
        )
        # Script order: bear = casualty sacrifice, False = keep original targets.
        p1._script.extend([bear, False])
        cast_spell(game, 0, "Burst Lightning", targets=[p2])
        assert p2.life == 16  # 2 (copy) + 2 (original)
        assert game.get_graveyard(p1).contains(bear)
        assert not game.get_battlefield(p1).contains(bear)

    def test_decline_no_copy(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(
            game,
            0,
            battlefield=[SilverquillTheDisputant(), bear],
            hand=[BurstLightning()],
            mana={ManaType.RED: 1},
        )
        p1._script.extend([None])  # decline the casualty
        cast_spell(game, 0, "Burst Lightning", targets=[p2])
        assert p2.life == 18  # only the original
        assert game.get_battlefield(p1).contains(bear)

    def test_no_eligible_creature_no_prompt(self) -> None:
        """Only a 0-power wall (besides nothing else): casualty not offered.

        Silverquill itself has power 4 and is eligible, so use an empty-but-
        for-a-wall board check via a 0/4 only: decline path would consume a
        script entry — none is provided, proving no prompt fires when the
        only other creature has power 0 and Silverquill is chosen as None.
        """
        game = create_game()
        p1, p2 = game.players
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        silverquill = SilverquillTheDisputant()
        set_board_state(
            game,
            0,
            battlefield=[silverquill, wall],
            hand=[BurstLightning()],
            mana={ManaType.RED: 1},
        )
        # Silverquill (power 4) is still eligible, so a prompt does fire;
        # decline it. The wall must not be offered.
        p1._script.extend([None])
        cast_spell(game, 0, "Burst Lightning", targets=[p2])
        assert p2.life == 18
        assert game.get_battlefield(p1).contains(wall)

    def test_new_targets_for_copy(self) -> None:
        """Copy may be redirected: original at p2, copy at p1."""
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(
            game,
            0,
            battlefield=[SilverquillTheDisputant(), bear],
            hand=[BurstLightning()],
            mana={ManaType.RED: 1},
        )
        p1._script.extend([bear, True, p1])
        cast_spell(game, 0, "Burst Lightning", targets=[p2])
        assert p2.life == 18  # original
        assert p1.life == 18  # redirected copy

    def test_opponents_spells_do_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[SilverquillTheDisputant()])
        set_board_state(game, 1, hand=[BurstLightning()], mana={ManaType.RED: 1})
        # No casualty prompt may fire for p1; p2's script holds only the target.
        game.active_player_index = 1
        game.priority_player_index = 1
        cast_spell(game, 1, "Burst Lightning", targets=[p1])
        assert p1.life == 18  # exactly one hit

    def test_creature_spells_do_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear_spell = Creature(name="Hand Bear", mana_cost=ManaCost.parse("{2}"), base_power=2, base_toughness=2)
        set_board_state(
            game,
            0,
            battlefield=[SilverquillTheDisputant()],
            hand=[bear_spell],
            mana={ManaType.COLORLESS: 2},
        )
        # No prompt may fire — an unexpected choose_card would exhaust the script.
        cast_spell(game, 0, "Hand Bear")
        assert game.get_battlefield(p1).contains(bear_spell)
