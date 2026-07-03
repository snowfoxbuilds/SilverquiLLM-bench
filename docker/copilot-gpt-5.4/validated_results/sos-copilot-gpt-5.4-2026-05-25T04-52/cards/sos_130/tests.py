"""Tests for SOS 130 — Steal the Show."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_130.card_impl import StealTheShow
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestStealTheShowProperties:
    """Static card data should match the SOS 130 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(StealTheShow(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = StealTheShow(owner=None)

        assert card.name == "Steal the Show"
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestStealTheShowModes:
    """Steal the Show should expose its two printed modes."""

    def test_exposes_the_two_printed_modes(self) -> None:
        modes = StealTheShow(owner=None).get_modes()

        assert len(modes) == 2
        assert "discards any number of cards" in modes[0].description
        assert "instant and sorcery cards in your graveyard" in modes[1].description


class TestStealTheShowTargeting:
    """Target requirements should depend on the chosen mode or modes."""

    def test_first_mode_targets_a_single_player(self) -> None:
        game = create_game()
        spell = StealTheShow(owner=game.players[0], controller=game.players[0])
        spell.selected_modes = [0]  # type: ignore[attr-defined]
        reqs = spell.get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(game.players[0]) is True
        assert reqs[0].filter_fn(game.players[1]) is True
        assert reqs[0].filter_fn(CardImpl(name="Not a player")) is False

    def test_second_mode_targets_a_single_creature_or_planeswalker(self) -> None:
        game = create_game()
        spell = StealTheShow(owner=game.players[0], controller=game.players[0])
        spell.selected_modes = [1]  # type: ignore[attr-defined]
        reqs = spell.get_targets(game)
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        planeswalker = Planeswalker(name="Visitor", starting_loyalty=3)

        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(creature) is True
        assert reqs[0].filter_fn(planeswalker) is True
        assert reqs[0].filter_fn(CardImpl(name="Lecture Notes")) is False

    def test_choosing_both_modes_requires_both_targets(self) -> None:
        game = create_game()
        spell = StealTheShow(owner=game.players[0], controller=game.players[0])
        spell.selected_modes = [0, 1]  # type: ignore[attr-defined]
        reqs = spell.get_targets(game)

        assert len(reqs) == 2
        assert reqs[0].description == "target player"
        assert reqs[1].description == "target creature or planeswalker"


class TestStealTheShowResolution:
    """Each chosen mode should resolve as printed, including choosing both."""

    def test_first_mode_target_player_discards_any_number_then_draws_that_many(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card_a = CardImpl(name="Card A", owner=p2, controller=p2)
        card_b = CardImpl(name="Card B", owner=p2, controller=p2)
        card_c = CardImpl(name="Card C", owner=p2, controller=p2)
        draw_one = CardImpl(name="Draw One", owner=p2, controller=p2)
        draw_two = CardImpl(name="Draw Two", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[card_a, card_b, card_c])
        game.get_library(p2).add(draw_one)
        game.get_library(p2).add(draw_two)
        p2._script.extend([True, card_a, True, card_c, False])

        spell = StealTheShow(owner=p1, controller=p1)
        spell.selected_modes = [0]  # type: ignore[attr-defined]
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert not game.get_hand(p2).contains(card_a)
        assert game.get_hand(p2).contains(card_b)
        assert not game.get_hand(p2).contains(card_c)
        assert game.get_hand(p2).contains(draw_one)
        assert game.get_hand(p2).contains(draw_two)
        assert game.get_graveyard(p2).contains(card_a)
        assert game.get_graveyard(p2).contains(card_c)

    def test_first_mode_can_choose_zero_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        kept = CardImpl(name="Kept Card", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[kept])
        p2._script.append(False)

        spell = StealTheShow(owner=p1, controller=p1)
        spell.selected_modes = [0]  # type: ignore[attr-defined]
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_hand(p2).get_all() == [kept]
        assert game.get_graveyard(p2).get_all() == []

    def test_second_mode_deals_damage_equal_to_your_instant_and_sorcery_count_in_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        instant_card = Instant(name="Burning Note", owner=p1, controller=p1)
        sorcery_card = Sorcery(name="Stage Fright", owner=p1, controller=p1)
        creature_card = Creature(
            name="Not Counted",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 0, graveyard=[instant_card, sorcery_card, creature_card])
        set_board_state(game, 1, battlefield=[target])

        spell = StealTheShow(owner=p1, controller=p1)
        spell.selected_modes = [1]  # type: ignore[attr-defined]
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 2

    def test_choosing_both_modes_applies_both_effects(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell_card = Instant(name="Counted Spell", owner=p1, controller=p1)
        discarded = CardImpl(name="Throwaway Page", owner=p2, controller=p2)
        drawn = CardImpl(name="Replacement Page", owner=p2, controller=p2)
        target = Creature(
            name="Stagehand",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, graveyard=[spell_card])
        set_board_state(game, 1, battlefield=[target], hand=[discarded])
        game.get_library(p2).add(drawn)
        p2._script.extend([True, discarded, False])

        spell = StealTheShow(owner=p1, controller=p1)
        spell.selected_modes = [0, 1]  # type: ignore[attr-defined]
        spell.chosen_targets = [p2, target]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(discarded)
        assert game.get_hand(p2).contains(drawn)
        assert target.damage_marked == 1
