"""Tests for SOS 233 — Startled Relic Sloth.

Creature — Sloth Beast {2}{R}{W} 4/4
Trample, lifelink
At the beginning of combat on your turn, exile up to one target card from a graveyard.
"""

from __future__ import annotations

from cards.sos.sos_233.card_impl import StartledRelicSloth
from engine.card import Creature
from engine.types import ManaCost, ManaType, Keyword, Zone
from test_utils import create_game, set_board_state


class TestStartledRelicSlothProperties:
    """Static card data should match the SOS 233 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(StartledRelicSloth(owner=None), Creature)

    def test_name(self) -> None:
        assert StartledRelicSloth(owner=None).name == "Startled Relic Sloth"

    def test_mana_cost(self) -> None:
        assert StartledRelicSloth(owner=None).mana_cost == ManaCost.parse("{2}{R}{W}")

    def test_power_toughness(self) -> None:
        card = StartledRelicSloth(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_trample(self) -> None:
        assert Keyword.TRAMPLE in StartledRelicSloth(owner=None).keywords

    def test_has_lifelink(self) -> None:
        assert Keyword.LIFELINK in StartledRelicSloth(owner=None).keywords


class TestStartledRelicSlothCombatTrigger:
    """At beginning of combat, exile up to one target card from a graveyard."""

    def test_exiles_card_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        sloth = StartledRelicSloth(owner=p1, controller=p1)
        target_card = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sloth])
        set_board_state(game, 1, graveyard=[target_card])
        # Trigger the combat ability targeting the graveyard card
        sloth.on_begin_combat(game, target=target_card)
        # Card should be exiled (removed from graveyard)
        gy = game.get_graveyard(p2).get_all()
        assert target_card not in gy

    def test_up_to_one_can_choose_zero(self) -> None:
        """'Up to one' means you can choose no targets."""
        game = create_game()
        p1 = game.players[0]
        sloth = StartledRelicSloth(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sloth])
        # Should not error when choosing no target
        sloth.on_begin_combat(game, target=None)

    def test_can_exile_from_own_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sloth = StartledRelicSloth(owner=p1, controller=p1)
        target_card = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sloth], graveyard=[target_card])
        sloth.on_begin_combat(game, target=target_card)
        gy = game.get_graveyard(p1).get_all()
        assert target_card not in gy
