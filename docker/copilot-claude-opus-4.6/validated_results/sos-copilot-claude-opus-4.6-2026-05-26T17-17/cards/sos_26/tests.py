"""Tests for SOS 26 — Primary Research."""

from __future__ import annotations

import pytest
from cards.sos.sos_26.card_impl import PrimaryResearch
from engine.card import Enchantment, Creature
from engine.types import CardType, ManaCost, ManaType, Zone, TargetRequirement
from test_utils import create_game, set_board_state, cast_spell


class TestPrimaryResearchProperties:
    """Static card data should match the SOS 26 spec."""

    def test_is_enchantment(self) -> None:
        assert isinstance(PrimaryResearch(owner=None), Enchantment)

    def test_name(self) -> None:
        assert PrimaryResearch(owner=None).name == "Primary Research"

    def test_mana_cost(self) -> None:
        assert PrimaryResearch(owner=None).mana_cost == ManaCost.parse("{4}{W}")


class TestPrimaryResearchETBTrigger:
    """When this enters, return target nonland permanent card with MV 3 or less from graveyard to battlefield."""

    def test_etb_returns_creature_from_graveyard_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.mana_cost = ManaCost.parse("{1}{G}")
        set_board_state(game, 0, graveyard=[bear], hand=[PrimaryResearch(owner=p1)],
                        mana={ManaType.WHITE: 5, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Primary Research", targets=[bear])
        # Bear should be on the battlefield
        bf = game.get_battlefield(p1)
        assert bear in bf

    def test_etb_cannot_target_card_with_mv_greater_than_3(self) -> None:
        game = create_game()
        p1 = game.players[0]
        big = Creature(name="Big Angel", owner=p1, controller=p1, base_power=5, base_toughness=5)
        big.card_types = {CardType.CREATURE}
        big.mana_cost = ManaCost.parse("{3}{W}{W}")  # MV = 5
        set_board_state(game, 0, graveyard=[big], hand=[PrimaryResearch(owner=p1)],
                        mana={ManaType.WHITE: 5, ManaType.COLORLESS: 4})
        # The ETB target should not allow MV > 3
        spell = PrimaryResearch(owner=p1, controller=p1)
        reqs = spell.get_targets(game)
        assert len(reqs) >= 1
        req = reqs[0]
        assert req.filter_fn(big) is False

    def test_etb_cannot_target_land_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from engine.card import CardImpl
        land = CardImpl(name="Plains", owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        land.mana_cost = ManaCost.parse("{0}")
        set_board_state(game, 0, graveyard=[land])
        spell = PrimaryResearch(owner=p1, controller=p1)
        reqs = spell.get_targets(game)
        req = reqs[0]
        assert req.filter_fn(land) is False

    def test_etb_target_zone_is_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = PrimaryResearch(owner=p1, controller=p1)
        reqs = spell.get_targets(game)
        assert reqs[0].zone == Zone.GRAVEYARD


class TestPrimaryResearchEndStepTrigger:
    """At beginning of your end step, if a card left your graveyard this turn, draw a card."""

    def test_draws_card_when_card_left_graveyard_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchant = PrimaryResearch(owner=p1, controller=p1)
        game.get_battlefield(p1).add(enchant)
        # Simulate a card leaving graveyard this turn
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.register_graveyard_leave(p1, bear)
        hand_before = len(game.get_hand(p1))
        # Trigger end step
        from test_utils import advance_to_phase
        from engine.types import Phase, Step
        advance_to_phase(game, Phase.ENDING, Step.END)
        hand_after = len(game.get_hand(p1))
        assert hand_after == hand_before + 1

    def test_no_draw_when_no_card_left_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchant = PrimaryResearch(owner=p1, controller=p1)
        game.get_battlefield(p1).add(enchant)
        hand_before = len(game.get_hand(p1))
        from test_utils import advance_to_phase
        from engine.types import Phase, Step
        advance_to_phase(game, Phase.ENDING, Step.END)
        hand_after = len(game.get_hand(p1))
        assert hand_after == hand_before
