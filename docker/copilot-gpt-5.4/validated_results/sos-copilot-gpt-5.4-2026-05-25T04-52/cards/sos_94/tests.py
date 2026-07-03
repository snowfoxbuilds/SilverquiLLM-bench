"""Tests for SOS 94 — Pox Plague."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_94.card_impl import PoxPlague
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestPoxPlagueProperties:
    """Static card data should match the SOS 94 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(PoxPlague(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = PoxPlague(owner=None)

        assert card.name == "Pox Plague"
        assert card.mana_cost == ManaCost.parse("{B}{B}{B}{B}{B}")


class TestPoxPlagueResolution:
    """Pox Plague should halve life, hands, and permanents with rounding down."""

    def test_each_player_loses_half_their_life_then_discards_and_sacrifices_half_of_their_choice_rounded_down(self) -> None:
        game = create_game()
        p1, p2 = game.players

        p1_keep_note = CardImpl(name="Keep Note", owner=p1, controller=p1)
        p1_keep_map = CardImpl(name="Keep Map", owner=p1, controller=p1)
        p1_discard = CardImpl(name="Discard Me", owner=p1, controller=p1)
        p1_keep_creature = Creature(name="Keep Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        p1_keep_land = Land(name="Keep Swamp", owner=p1, controller=p1)
        p1_sacrifice = Creature(name="Sacrifice Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)

        p2_keep_note = CardImpl(name="Keep Note A", owner=p2, controller=p2)
        p2_keep_map = CardImpl(name="Keep Note B", owner=p2, controller=p2)
        p2_discard_a = CardImpl(name="Discard A", owner=p2, controller=p2)
        p2_discard_b = CardImpl(name="Discard B", owner=p2, controller=p2)
        p2_keep_creature = Creature(name="Keep Bear A", owner=p2, controller=p2, base_power=2, base_toughness=2)
        p2_keep_land = Land(name="Keep Swamp", owner=p2, controller=p2)
        p2_keep_other = Creature(name="Keep Bear B", owner=p2, controller=p2, base_power=2, base_toughness=2)
        p2_sacrifice_a = Creature(name="Sacrifice Bear A", owner=p2, controller=p2, base_power=2, base_toughness=2)
        p2_sacrifice_b = Land(name="Sacrifice Swamp", owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            hand=[p1_keep_note, p1_keep_map, p1_discard],
            battlefield=[p1_keep_creature, p1_keep_land, p1_sacrifice],
            life=21,
        )
        set_board_state(
            game,
            1,
            hand=[p2_keep_note, p2_keep_map, p2_discard_a, p2_discard_b],
            battlefield=[p2_keep_creature, p2_keep_land, p2_keep_other, p2_sacrifice_a, p2_sacrifice_b],
            life=9,
        )
        p1._script.extend([p1_discard, p1_sacrifice])
        p2._script.extend([p2_discard_a, p2_discard_b, p2_sacrifice_a, p2_sacrifice_b])

        PoxPlague(owner=p1, controller=p1).on_resolve(game)

        assert p1.life == 11
        assert p2.life == 5

        assert game.get_graveyard(p1).contains(p1_discard)
        assert game.get_graveyard(p1).contains(p1_sacrifice)
        assert game.get_hand(p1).get_all() == [p1_keep_note, p1_keep_map]
        assert game.get_battlefield(p1).get_all() == [p1_keep_creature, p1_keep_land]

        assert game.get_graveyard(p2).contains(p2_discard_a)
        assert game.get_graveyard(p2).contains(p2_discard_b)
        assert game.get_graveyard(p2).contains(p2_sacrifice_a)
        assert game.get_graveyard(p2).contains(p2_sacrifice_b)
        assert game.get_hand(p2).get_all() == [p2_keep_note, p2_keep_map]
        assert game.get_battlefield(p2).get_all() == [p2_keep_creature, p2_keep_land, p2_keep_other]

    def test_rounds_down_so_single_life_card_or_permanent_is_untouched(self) -> None:
        game = create_game()
        p1, p2 = game.players
        p1_hand = CardImpl(name="Only Card", owner=p1, controller=p1)
        p2_hand = CardImpl(name="Only Card", owner=p2, controller=p2)
        p1_perm = Creature(name="Only Bear", owner=p1, controller=p1, base_power=1, base_toughness=1)
        p2_perm = Land(name="Only Swamp", owner=p2, controller=p2)

        set_board_state(game, 0, hand=[p1_hand], battlefield=[p1_perm], life=1)
        set_board_state(game, 1, hand=[p2_hand], battlefield=[p2_perm], life=2)

        PoxPlague(owner=p1, controller=p1).on_resolve(game)

        assert p1.life == 1
        assert p2.life == 1
        assert game.get_hand(p1).get_all() == [p1_hand]
        assert game.get_hand(p2).get_all() == [p2_hand]
        assert game.get_battlefield(p1).get_all() == [p1_perm]
        assert game.get_battlefield(p2).get_all() == [p2_perm]
