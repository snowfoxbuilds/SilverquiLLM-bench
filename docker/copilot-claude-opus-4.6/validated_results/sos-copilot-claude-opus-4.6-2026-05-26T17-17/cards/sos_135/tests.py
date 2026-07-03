"""Tests for SOS 135 — Tome Blast.

A Sorcery for {1}{R} that deals 2 damage to any target.
Flashback {4}{R} (You may cast this card from your graveyard for its flashback
cost. Then exile it.)
"""

from __future__ import annotations

from cards.sos.sos_135.card_impl import TomeBlast
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTomeBlastProperties:
    """Static card data should match the SOS 135 spec."""

    def test_is_sorcery(self) -> None:
        card = TomeBlast(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TomeBlast(owner=None)
        assert card.name == "Tome Blast"

    def test_mana_cost(self) -> None:
        card = TomeBlast(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_has_flashback(self) -> None:
        card = TomeBlast(owner=None)
        assert Keyword.FLASHBACK in card.keywords

    def test_flashback_cost(self) -> None:
        card = TomeBlast(owner=None)
        assert card.flashback_cost == ManaCost.parse("{4}{R}")


class TestTomeBlastResolution:
    """Tome Blast deals 2 damage to any target."""

    def test_deals_2_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", owner=p2, controller=p2,
                          base_power=2, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])

        spell = TomeBlast(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        assert target.damage_taken == 2

    def test_deals_2_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        life_before = p2.life

        spell = TomeBlast(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)
        assert p2.life == life_before - 2

    def test_no_target_is_noop(self) -> None:
        """If no target is chosen, resolution should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = TomeBlast(owner=p1, controller=p1)
        spell.on_resolve(game)  # Should not raise


class TestTomeBlastFlashback:
    """Flashback allows casting from graveyard then exiling."""

    def test_can_be_cast_from_graveyard(self) -> None:
        """Card should be castable from graveyard via flashback."""
        game = create_game()
        p1 = game.players[0]
        card = TomeBlast(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        # Card in graveyard should indicate it can be cast with flashback
        assert card.can_cast_with_flashback(game) is True

    def test_exiled_after_flashback_resolves(self) -> None:
        """After resolving via flashback, the card is exiled."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TomeBlast(owner=p1, controller=p1)
        card.is_flashback_cast = True
        card.chosen_targets = [p2]
        card.on_resolve(game)
        # After flashback resolution, card should be marked for exile
        assert card.zone == Zone.EXILE or getattr(card, 'exile_on_resolve', False)
