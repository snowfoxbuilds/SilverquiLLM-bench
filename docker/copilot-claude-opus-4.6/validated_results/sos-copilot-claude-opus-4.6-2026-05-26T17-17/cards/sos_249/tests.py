"""Tests for SOS 249 — Mage Tower Referee.

Artifact Creature — Construct  {2}
2/1
Oracle: Whenever you cast a multicolored spell, put a +1/+1 counter on
this creature.
"""

from __future__ import annotations

from cards.sos.sos_249.card_impl import MageTowerReferee
from engine.card import Creature
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


class TestMageTowerRefereeProperties:
    """Static card data should match the SOS 249 spec."""

    def test_name(self) -> None:
        card = MageTowerReferee(owner=None)
        assert card.name == "Mage Tower Referee"

    def test_mana_cost(self) -> None:
        card = MageTowerReferee(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}")

    def test_power_toughness(self) -> None:
        card = MageTowerReferee(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_is_creature(self) -> None:
        card = MageTowerReferee(owner=None)
        assert isinstance(card, Creature)

    def test_subtypes(self) -> None:
        card = MageTowerReferee(owner=None)
        subtypes = getattr(card, "subtypes", set())
        assert "Construct" in subtypes


class TestMageTowerRefereeTriggeredAbility:
    """Whenever you cast a multicolored spell, put a +1/+1 counter on this."""

    def test_has_triggered_ability(self) -> None:
        card = MageTowerReferee(owner=None)
        assert hasattr(card, "on_spell_cast") or hasattr(card, "get_triggers")

    def test_multicolored_spell_adds_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MageTowerReferee(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        before = card.plus_one_counters
        card.on_spell_cast(game, spell_colors=["R", "U"])  # multicolored
        assert card.plus_one_counters == before + 1

    def test_monocolored_spell_does_not_add_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MageTowerReferee(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        before = card.plus_one_counters
        card.on_spell_cast(game, spell_colors=["R"])  # mono
        assert card.plus_one_counters == before

    def test_colorless_spell_does_not_add_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MageTowerReferee(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        before = card.plus_one_counters
        card.on_spell_cast(game, spell_colors=[])  # colorless
        assert card.plus_one_counters == before

    def test_multiple_multicolored_spells_add_multiple_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MageTowerReferee(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.on_spell_cast(game, spell_colors=["W", "B"])
        card.on_spell_cast(game, spell_colors=["U", "G"])
        card.on_spell_cast(game, spell_colors=["R", "W", "B"])
        assert card.plus_one_counters == 3

    def test_counters_increase_effective_power_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MageTowerReferee(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.on_spell_cast(game, spell_colors=["R", "G"])
        # After one +1/+1 counter, should be 3/2
        assert card.power == 3
        assert card.toughness == 2
