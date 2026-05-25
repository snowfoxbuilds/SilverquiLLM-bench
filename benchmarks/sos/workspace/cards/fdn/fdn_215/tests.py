"""Reference test for FDN 215 — Bushwhack.

Illustrative test covering **modal-choice / mode selection** mechanics.
Bushwhack is a "Choose one" sorcery; the active mode is recorded on the
card as ``chosen_mode`` (an int index into ``get_modes()``) and
``on_resolve`` dispatches on that value.
"""

from __future__ import annotations

from benchmarks.sos.workspace.cards.fdn.fdn_215.card_impl import Bushwhack
from benchmarks.sos.workspace.engine.card import Mode, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Supertype, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestBushwhackProperties:
    """Static card data should match the FDN 215 spec."""

    def test_is_sorcery(self) -> None:
        card = Bushwhack(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert Bushwhack(owner=None).name == "Bushwhack"

    def test_mana_cost(self) -> None:
        assert Bushwhack(owner=None).mana_cost == ManaCost.parse("{G}")


class TestBushwhackModalDeclaration:
    """get_modes() should declare exactly two modes."""

    def test_returns_two_modes(self) -> None:
        modes = Bushwhack(owner=None).get_modes()
        assert len(modes) == 2

    def test_each_mode_is_mode_instance(self) -> None:
        modes = Bushwhack(owner=None).get_modes()
        for m in modes:
            assert isinstance(m, Mode)


class TestBushwhackModeSelection:
    """chosen_mode drives the on_resolve branch."""

    def test_chosen_mode_defaults_to_none(self) -> None:
        card = Bushwhack(owner=None)
        assert card.chosen_mode is None

    def test_chosen_mode_zero_runs_land_search(self) -> None:
        """Mode 0 = search library for a basic land. With no basic lands
        in the library, the search no-ops but does not raise."""
        from benchmarks.sos.workspace.engine.card import CardImpl

        game = create_game()
        p1 = game.players[0]
        # Library is empty — search will find nothing but should not crash.
        card = Bushwhack(owner=p1, controller=p1)
        card.chosen_mode = 0
        card.on_resolve(game)
        # No card moved to hand.
        assert len(p1.zones[Zone.HAND].get_all()) == 0

    def test_chosen_mode_one_runs_fight_branch(self) -> None:
        """Mode 1 = fight. With no chosen_targets, the fight branch no-ops."""
        game = create_game()
        p1 = game.players[0]
        card = Bushwhack(owner=p1, controller=p1)
        card.chosen_mode = 1
        # No chosen_targets — fight branch exits without dealing damage.
        card.on_resolve(game)

    def test_no_mode_skips_resolution(self) -> None:
        """When chosen_mode is None, on_resolve returns immediately."""
        game = create_game()
        p1 = game.players[0]
        card = Bushwhack(owner=p1, controller=p1)
        # chosen_mode left as None.
        card.on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) == 0
