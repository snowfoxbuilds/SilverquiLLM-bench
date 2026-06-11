"""Tests for SOS 83 — Foolish Fate."""

from __future__ import annotations

from cards.sos.sos_83.card_impl import FoolishFate
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestFoolishFateProperties:
    """Static card data should match the SOS 83 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(FoolishFate(owner=None), Instant)

    def test_name(self) -> None:
        assert FoolishFate(owner=None).name == "Foolish Fate"

    def test_mana_cost(self) -> None:
        assert FoolishFate(owner=None).mana_cost == ManaCost.parse("{2}{B}")


class TestFoolishFateTargeting:
    """Targets a creature."""

    def test_returns_target_requirement_for_creature(self) -> None:
        game = create_game()
        reqs = FoolishFate(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD


class TestFoolishFateResolution:
    """Destroys target creature; infusion causes life loss."""

    def test_destroys_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(name="Grizzly Bears", owner=p2, controller=p2,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[bear])

        spell = FoolishFate(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Bear should be destroyed (in graveyard)
        bf = game.get_battlefield(p2)
        bf_names = [c.name for c in bf.cards] if hasattr(bf, 'cards') else [c.name for c in bf]
        assert "Grizzly Bears" not in bf_names

    def test_infusion_causes_life_loss_when_life_gained(self) -> None:
        """If controller gained life this turn, opponent loses 3 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Mark that p1 gained life this turn
        p1.life_gained_this_turn = 3

        bear = Creature(name="Grizzly Bears", owner=p2, controller=p2,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[bear], life=20)

        spell = FoolishFate(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Opponent loses 3 life from infusion
        assert p2.life == 17

    def test_no_infusion_without_life_gain(self) -> None:
        """Without life gain this turn, no extra life loss."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # No life gained this turn
        p1.life_gained_this_turn = 0

        bear = Creature(name="Grizzly Bears", owner=p2, controller=p2,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[bear], life=20)

        spell = FoolishFate(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # No extra life loss
        assert p2.life == 20
