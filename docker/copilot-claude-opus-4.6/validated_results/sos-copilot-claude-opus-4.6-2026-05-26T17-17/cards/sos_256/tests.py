"""Tests for SOS 256 — Forum of Amity.

Land that enters tapped, taps for {W} or {B}, and has a {2}{W}{B},{T} surveil 1 ability.
"""

from __future__ import annotations

from cards.sos.sos_256.card_impl import ForumOfAmity
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game


class TestForumOfAmityProperties:
    """Static card data should match the SOS 256 spec."""

    def test_is_land(self) -> None:
        card = ForumOfAmity(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = ForumOfAmity(owner=None)
        assert card.name == "Forum of Amity"

    def test_has_land_card_type(self) -> None:
        card = ForumOfAmity(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        """Lands have no mana cost."""
        card = ForumOfAmity(owner=None)
        assert card.mana_cost is None or str(card.mana_cost) == ""


class TestForumOfAmityEntersTapped:
    """This land enters tapped."""

    def test_enters_tapped(self) -> None:
        """The land should enter the battlefield tapped."""
        game = create_game()
        p1 = game.players[0]
        card = ForumOfAmity(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True


class TestForumOfAmityManaAbilities:
    """'{T}: Add {W} or {B}.' — produces white or black mana."""

    def test_has_mana_abilities(self) -> None:
        card = ForumOfAmity(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_white(self) -> None:
        """At least one mana ability produces white mana."""
        card = ForumOfAmity(owner=None)
        abilities = card.get_mana_abilities()
        white_found = any(
            ManaType.WHITE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert white_found is True

    def test_can_produce_black(self) -> None:
        """At least one mana ability produces black mana."""
        card = ForumOfAmity(owner=None)
        abilities = card.get_mana_abilities()
        black_found = any(
            ManaType.BLACK in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert black_found is True


class TestForumOfAmitySurveilAbility:
    """'{2}{W}{B}, {T}: Surveil 1.' — activated ability that surveils."""

    def test_has_activated_abilities(self) -> None:
        """The card should expose at least one activated (non-mana) ability."""
        card = ForumOfAmity(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_surveil_puts_top_card_to_graveyard(self) -> None:
        """Surveil 1: look at top card, may put to graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = ForumOfAmity(owner=p1, controller=p1)
        from engine.card import CardImpl
        top_card = CardImpl(name="TopCard", owner=p1)
        game.get_battlefield(p1).add(card)
        card.is_tapped = False
        # Set library with a known top card
        from test_utils import set_board_state
        set_board_state(game, 0, library=[top_card])
        # Activate the surveil ability (player chooses to put card in GY)
        abilities = card.get_activated_abilities()
        surveil_ability = abilities[0]
        surveil_ability.activate(game, card, p1, choice="graveyard")
        graveyard = game.get_graveyard(p1).get_all()
        assert any(c.name == "TopCard" for c in graveyard)
