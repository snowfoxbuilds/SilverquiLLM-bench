"""Tests for SOS 144 — Efflorescence."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_144.card_impl import Efflorescence
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEfflorescenceProperties:
    """Static card data should match the SOS 144 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Efflorescence(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = Efflorescence(owner=None)

        assert card.name == "Efflorescence"
        assert card.mana_cost == ManaCost.parse("{2}{G}")


class TestEfflorescenceTargeting:
    """Efflorescence should target a creature on the battlefield."""

    def test_returns_a_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = Efflorescence(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = Efflorescence(owner=None).get_targets(game)[0]

        creature = Creature(name="Helpful Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestEfflorescenceResolution:
    """Efflorescence should always add counters and conditionally grant keywords."""

    def test_on_resolve_puts_two_plus_one_plus_one_counters_on_the_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[target])

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.plus_one_counters == 2
        assert target.power == 4
        assert target.toughness == 4
        assert Keyword.TRAMPLE not in target.keywords
        assert Keyword.INDESTRUCTIBLE not in target.keywords

    def test_if_you_gained_life_this_turn_it_also_grants_trample_and_indestructible_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[target])
        p1.life_gained_this_turn = 1

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.plus_one_counters == 2
        assert target.power == 4
        assert target.toughness == 4
        assert Keyword.TRAMPLE in target.keywords
        assert Keyword.INDESTRUCTIBLE in target.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.plus_one_counters == 2
        assert target.power == 4
        assert target.toughness == 4
        assert Keyword.TRAMPLE not in target.keywords
        assert Keyword.INDESTRUCTIBLE not in target.keywords
