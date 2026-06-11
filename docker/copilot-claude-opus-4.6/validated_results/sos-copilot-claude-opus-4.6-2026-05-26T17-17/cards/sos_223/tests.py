"""Tests for SOS 223 — Sanar, Unfinished Genius // Wild Idea.

Front face: Legendary Creature — Goblin Sorcerer, {U}{R}, 0/4
- Enters prepared.
- {T}: Create a Treasure token. Activate only if you've cast an instant or
  sorcery spell this turn.

Back face: Wild Idea — Sorcery, {3}{U}{R}
- (The prepared mechanic lets you cast a copy of the spell side while prepared.)
"""

from __future__ import annotations

from cards.sos.sos_223.card_impl import SanarUnfinishedGeniusWildIdea
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSanarProperties:
    """Static card data should match the SOS 223 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SanarUnfinishedGeniusWildIdea(owner=None), Creature)

    def test_name(self) -> None:
        assert SanarUnfinishedGeniusWildIdea(owner=None).name == "Sanar, Unfinished Genius"

    def test_mana_cost(self) -> None:
        assert SanarUnfinishedGeniusWildIdea(owner=None).mana_cost == ManaCost.parse("{U}{R}")

    def test_power_toughness(self) -> None:
        card = SanarUnfinishedGeniusWildIdea(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 4

    def test_has_prepared_keyword(self) -> None:
        card = SanarUnfinishedGeniusWildIdea(owner=None)
        assert Keyword.PREPARED in card.keywords


class TestSanarEntersPrepared:
    """Sanar enters prepared."""

    def test_enters_battlefield_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sanar = SanarUnfinishedGeniusWildIdea(owner=p1, controller=p1)
        sanar.enter_battlefield(game)
        assert sanar.is_prepared is True


class TestSanarTreasureAbility:
    """{T}: Create a Treasure token. Activate only if you've cast an instant
    or sorcery spell this turn."""

    def test_cannot_activate_without_instant_sorcery_cast(self) -> None:
        """If no instant/sorcery was cast this turn, ability cannot activate."""
        game = create_game()
        p1 = game.players[0]
        sanar = SanarUnfinishedGeniusWildIdea(owner=p1, controller=p1)
        sanar.is_tapped = False
        game.get_battlefield(p1).add(sanar)
        assert sanar.can_activate_treasure(game) is False

    def test_can_activate_after_instant_sorcery_cast(self) -> None:
        """If an instant or sorcery was cast this turn, ability is active."""
        game = create_game()
        p1 = game.players[0]
        sanar = SanarUnfinishedGeniusWildIdea(owner=p1, controller=p1)
        sanar.is_tapped = False
        game.get_battlefield(p1).add(sanar)
        # Mark that an instant/sorcery was cast this turn
        game.spells_cast_this_turn.append({"controller": p1, "types": {"instant"}})
        assert sanar.can_activate_treasure(game) is True

    def test_treasure_ability_creates_treasure_token(self) -> None:
        """Activating creates a Treasure token on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        sanar = SanarUnfinishedGeniusWildIdea(owner=p1, controller=p1)
        sanar.is_tapped = False
        game.get_battlefield(p1).add(sanar)
        game.spells_cast_this_turn.append({"controller": p1, "types": {"instant"}})

        bf_before = len(game.get_battlefield(p1).cards)
        sanar.activate_treasure(game)
        bf_after = len(game.get_battlefield(p1).cards)
        assert bf_after == bf_before + 1  # new treasure token

    def test_treasure_ability_taps_sanar(self) -> None:
        """Ability costs {T}, so Sanar becomes tapped."""
        game = create_game()
        p1 = game.players[0]
        sanar = SanarUnfinishedGeniusWildIdea(owner=p1, controller=p1)
        sanar.is_tapped = False
        game.get_battlefield(p1).add(sanar)
        game.spells_cast_this_turn.append({"controller": p1, "types": {"instant"}})

        sanar.activate_treasure(game)
        assert sanar.is_tapped is True
