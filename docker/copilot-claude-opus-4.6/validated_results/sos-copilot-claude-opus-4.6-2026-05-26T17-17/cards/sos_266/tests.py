"""Tests for SOS 266 — Titan's Grave.

Land:
- This land enters tapped.
- {T}: Add {B} or {G}.
- {2}{B}{G}, {T}: Surveil 1.
"""

from __future__ import annotations

from cards.sos.sos_266.card_impl import TitansGrave
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTitansGraveProperties:
    """Static card data should match the SOS 266 spec."""

    def test_is_land(self) -> None:
        card = TitansGrave(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = TitansGrave(owner=None)
        assert card.name == "Titan's Grave"

    def test_has_land_card_type(self) -> None:
        card = TitansGrave(owner=None)
        assert CardType.LAND in card.card_types


class TestTitansGraveEntersTapped:
    """This land enters tapped — always."""

    def test_enters_tapped_with_no_board(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TitansGrave(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_tapped_even_with_other_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Swamp", owner=p1, controller=p1)
        land2 = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2])
        card = TitansGrave(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True


class TestTitansGraveManaAbilities:
    """{T}: Add {B} or {G}."""

    def test_has_mana_abilities(self) -> None:
        card = TitansGrave(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_black(self) -> None:
        card = TitansGrave(owner=None)
        abilities = card.get_mana_abilities()
        black_found = any(
            ManaType.BLACK in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert black_found is True

    def test_can_produce_green(self) -> None:
        card = TitansGrave(owner=None)
        abilities = card.get_mana_abilities()
        green_found = any(
            ManaType.GREEN in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert green_found is True


class TestTitansGraveSurveilAbility:
    """{2}{B}{G}, {T}: Surveil 1."""

    def test_has_activated_ability(self) -> None:
        card = TitansGrave(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_surveil_moves_top_card_to_graveyard(self) -> None:
        """Activating the surveil ability should allow putting top card
        into graveyard."""
        from engine.card import Land as LandCard

        game = create_game()
        p1 = game.players[0]
        card = TitansGrave(owner=p1, controller=p1)
        card.is_tapped = False
        set_board_state(game, 0, battlefield=[card])

        # Put a card on top of library
        filler = LandCard(name="Forest", owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(filler)

        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        # The surveil ability should exist
        surveil_ability = abilities[0]
        # Activate it - implementation should surveil 1
        surveil_ability.activate(game=game, source=card, player=p1)

        # After surveil, card should be in graveyard (if chosen to put there)
        graveyard_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert filler in graveyard_cards
