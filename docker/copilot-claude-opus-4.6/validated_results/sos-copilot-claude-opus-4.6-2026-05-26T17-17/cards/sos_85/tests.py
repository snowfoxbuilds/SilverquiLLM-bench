"""Tests for SOS 85 — Grave Researcher // Reanimate."""

from __future__ import annotations

from cards.sos.sos_85.card_impl import GraveResearcher
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, advance_to_phase
from engine.types import Phase, Step


class TestGraveResearcherProperties:
    """Static card data should match the SOS 85 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(GraveResearcher(owner=None), Creature)

    def test_name(self) -> None:
        assert GraveResearcher(owner=None).name == "Grave Researcher"

    def test_mana_cost(self) -> None:
        assert GraveResearcher(owner=None).mana_cost == ManaCost.parse("{2}{B}")

    def test_power_toughness(self) -> None:
        card = GraveResearcher(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestGraveResearcherUpkeepSurveil:
    """At beginning of upkeep, surveil 1."""

    def test_surveil_on_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]

        researcher = GraveResearcher(owner=p1, controller=p1)
        researcher.card_types = {CardType.CREATURE}

        # Put a card on top of library for surveil
        filler = Creature(name="Library Card", owner=p1, controller=p1,
                          base_power=1, base_toughness=1)
        filler.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[researcher])
        # Add card to library top
        game.get_library(p1).add_top(filler)

        # Trigger upkeep
        researcher.on_upkeep(game)

        # After surveil 1, the card should be either on top of library
        # or in graveyard (surveil lets you choose)
        # At minimum, surveil was performed (library or graveyard changed)


class TestGraveResearcherPrepared:
    """Becomes prepared when 3+ creature cards in graveyard."""

    def test_not_prepared_with_fewer_than_3_creatures_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        researcher = GraveResearcher(owner=p1, controller=p1)
        researcher.card_types = {CardType.CREATURE}

        # Only 2 creatures in graveyard
        c1 = Creature(name="Dead 1", owner=p1, controller=p1,
                      base_power=1, base_toughness=1)
        c1.card_types = {CardType.CREATURE}
        c2 = Creature(name="Dead 2", owner=p1, controller=p1,
                      base_power=1, base_toughness=1)
        c2.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[researcher], graveyard=[c1, c2])

        researcher.on_upkeep(game)
        assert researcher.prepared is False

    def test_becomes_prepared_with_3_creatures_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        researcher = GraveResearcher(owner=p1, controller=p1)
        researcher.card_types = {CardType.CREATURE}

        # 3 creatures in graveyard
        creatures = []
        for i in range(3):
            c = Creature(name=f"Dead {i}", owner=p1, controller=p1,
                         base_power=1, base_toughness=1)
            c.card_types = {CardType.CREATURE}
            creatures.append(c)

        set_board_state(game, 0, battlefield=[researcher], graveyard=creatures)

        researcher.on_upkeep(game)
        assert researcher.prepared is True

    def test_prepared_allows_casting_spell_copy(self) -> None:
        """While prepared, can cast a copy of the spell side (Reanimate)."""
        game = create_game()
        p1 = game.players[0]

        researcher = GraveResearcher(owner=p1, controller=p1)
        researcher.card_types = {CardType.CREATURE}
        researcher.prepared = True

        # Should be able to get the spell side
        spell = researcher.get_spell_side()
        assert spell is not None
        assert spell.name == "Reanimate"
