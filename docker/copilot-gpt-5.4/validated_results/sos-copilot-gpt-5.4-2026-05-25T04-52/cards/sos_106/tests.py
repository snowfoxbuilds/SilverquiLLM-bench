"""Tests for SOS 106 — Ancestral Anger."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_106.card_impl import AncestralAnger
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestAncestralAngerProperties:
    """Static card data should match the SOS 106 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(AncestralAnger(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = AncestralAnger(owner=None)
        assert card.name == "Ancestral Anger"
        assert card.mana_cost == ManaCost.parse("{R}")


class TestAncestralAngerTargeting:
    """Ancestral Anger should target a single creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = AncestralAnger(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = AncestralAnger(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestAncestralAngerResolution:
    """Ancestral Anger should buff the target based on matching graveyard cards and draw."""

    def test_target_gets_trample_plus_x_power_and_you_draw_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Storm Pupil",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        prior_copy_a = CardImpl(name="Ancestral Anger", owner=p1, controller=p1)
        prior_copy_b = CardImpl(name="Ancestral Anger", owner=p1, controller=p1)
        drawn = CardImpl(name="Fresh Lesson", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target], graveyard=[prior_copy_a, prior_copy_b])
        game.get_library(p1).add(drawn)

        spell = AncestralAnger(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.power == 5
        assert target.toughness == 2
        assert Keyword.TRAMPLE in target.keywords
        assert game.get_hand(p1).contains(drawn)

    def test_counts_only_cards_named_ancestral_anger_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Storm Pupil",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        matching = CardImpl(name="Ancestral Anger", owner=p1, controller=p1)
        non_matching = CardImpl(name="Other Spell", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target], graveyard=[matching, non_matching])

        spell = AncestralAnger(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.power == 4
        assert target.toughness == 2

    def test_trample_and_power_bonus_expire_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Storm Pupil",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        prior_copy = CardImpl(name="Ancestral Anger", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[target], graveyard=[prior_copy])

        spell = AncestralAnger(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)
        assert target.power == 4
        assert Keyword.TRAMPLE in target.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 2
        assert target.toughness == 2
        assert Keyword.TRAMPLE not in target.keywords
