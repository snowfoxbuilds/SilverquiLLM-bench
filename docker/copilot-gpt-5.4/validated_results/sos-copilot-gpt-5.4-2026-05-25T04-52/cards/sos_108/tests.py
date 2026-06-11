"""Tests for SOS 108 — Artistic Process."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_108.card_impl import ArtisticProcess
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestArtisticProcessProperties:
    """Static card data should match the SOS 108 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ArtisticProcess(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ArtisticProcess(owner=None)
        assert card.name == "Artistic Process"
        assert card.mana_cost == ManaCost.parse("{3}{R}{R}")


class TestArtisticProcessModes:
    """Artistic Process should expose the printed modal choices."""

    def test_exposes_three_printed_modes(self) -> None:
        modes = ArtisticProcess(owner=None).get_modes()

        assert len(modes) == 3
        assert "6 damage" in modes[0].description
        assert "2 damage to each creature you don't control" in modes[1].description
        assert "3/3 blue and red Elemental creature token" in modes[2].description

    def test_first_mode_targets_a_single_creature_on_the_battlefield(self) -> None:
        game = create_game()
        spell = ArtisticProcess(owner=None)
        spell.selected_mode = 0
        reqs = spell.get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")
        assert reqs[0].filter_fn(creature) is True
        assert reqs[0].filter_fn(non_creature) is False

    def test_second_and_third_modes_have_no_targets(self) -> None:
        game = create_game()
        second_mode_spell = ArtisticProcess(owner=None)
        second_mode_spell.selected_mode = 1
        third_mode_spell = ArtisticProcess(owner=None)
        third_mode_spell.selected_mode = 2

        assert second_mode_spell.get_targets(game) == []
        assert third_mode_spell.get_targets(game) == []


class TestArtisticProcessResolution:
    """Each Artistic Process mode should resolve as printed."""

    def test_first_mode_deals_six_damage_to_target_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=6,
            base_toughness=6,
        )
        set_board_state(game, 1, battlefield=[target])

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.selected_mode = 0
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.damage_marked == 6

    def test_second_mode_deals_two_damage_to_each_creature_you_dont_control_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        friendly = Creature(
            name="Friendly Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_a = Creature(
            name="Opposing A",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        opposing_b = Creature(
            name="Opposing B",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        set_board_state(game, 0, battlefield=[friendly])
        set_board_state(game, 1, battlefield=[opposing_a, opposing_b])

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.selected_mode = 1

        spell.on_resolve(game)

        assert friendly.damage_marked == 0
        assert opposing_a.damage_marked == 2
        assert opposing_b.damage_marked == 2

    def test_third_mode_creates_a_3_3_blue_and_red_elemental_with_flying_and_haste(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.selected_mode = 2

        spell.on_resolve(game)

        battlefield = game.get_battlefield(p1).get_all()
        assert len(battlefield) == 1
        token = battlefield[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert "Elemental" in token.subtypes
        assert get_colors(token) == {Color.BLUE, Color.RED}
        assert Keyword.FLYING in token.keywords
        assert Keyword.HASTE in token.keywords
        assert token.power == 3
        assert token.toughness == 3

    def test_third_mode_haste_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.selected_mode = 2

        spell.on_resolve(game)
        token = game.get_battlefield(p1).get_all()[0]
        assert Keyword.HASTE in token.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert Keyword.FLYING in token.keywords
        assert Keyword.HASTE not in token.keywords
        assert token.power == 3
        assert token.toughness == 3
