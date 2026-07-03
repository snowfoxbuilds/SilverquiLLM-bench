"""Tests for SOS 188 — Fix What's Broken.

Fix What's Broken is a {2}{W}{B} Sorcery:
"As an additional cost to cast this spell, pay X life.
Return each artifact and creature card with mana value X from your graveyard to the battlefield."
"""

from __future__ import annotations

from cards.sos.sos_188.card_impl import FixWhatsBroken
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestFixWhatsBrokenProperties:
    """Static card data should match the SOS 188 spec."""

    def test_name(self) -> None:
        assert FixWhatsBroken(owner=None).name == "Fix What's Broken"

    def test_mana_cost(self) -> None:
        assert FixWhatsBroken(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")


class TestFixWhatsBrokenResolution:
    """Returns artifacts and creatures with mana value X from graveyard."""

    def test_returns_creature_with_matching_mana_value(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Create a creature with mana value 3 in graveyard
        creature = Creature(name="Test Creature", owner=p1, base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        creature.mana_cost = ManaCost.parse("{2}{W}")  # mana value 3
        set_board_state(game, 0, graveyard=[creature], hand=[])

        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 3  # paid 3 life
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        assert creature in bf

    def test_returns_artifact_with_matching_mana_value(self) -> None:
        game = create_game()
        p1 = game.players[0]

        artifact = CardImpl(name="Test Artifact", owner=p1)
        artifact.card_types = {CardType.ARTIFACT}
        artifact.mana_cost = ManaCost.parse("{2}")  # mana value 2
        set_board_state(game, 0, graveyard=[artifact], hand=[])

        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 2
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        assert artifact in bf

    def test_does_not_return_non_matching_mana_value(self) -> None:
        game = create_game()
        p1 = game.players[0]

        creature = Creature(name="Expensive Creature", owner=p1, base_power=4, base_toughness=4)
        creature.card_types = {CardType.CREATURE}
        creature.mana_cost = ManaCost.parse("{4}{G}{G}")  # mana value 6
        set_board_state(game, 0, graveyard=[creature], hand=[])

        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 3  # doesn't match
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        assert creature not in bf

    def test_does_not_return_non_artifact_non_creature(self) -> None:
        """Enchantments and other types should not be returned."""
        game = create_game()
        p1 = game.players[0]

        enchantment = CardImpl(name="Some Enchantment", owner=p1)
        enchantment.card_types = {CardType.ENCHANTMENT}
        enchantment.mana_cost = ManaCost.parse("{2}{W}")  # mana value 3
        set_board_state(game, 0, graveyard=[enchantment], hand=[])

        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 3
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        assert enchantment not in bf

    def test_returns_multiple_cards_with_same_mana_value(self) -> None:
        game = create_game()
        p1 = game.players[0]

        creature1 = Creature(name="Creature A", owner=p1, base_power=2, base_toughness=2)
        creature1.card_types = {CardType.CREATURE}
        creature1.mana_cost = ManaCost.parse("{1}{W}")  # mana value 2

        creature2 = Creature(name="Creature B", owner=p1, base_power=3, base_toughness=1)
        creature2.card_types = {CardType.CREATURE}
        creature2.mana_cost = ManaCost.parse("{1}{B}")  # mana value 2

        set_board_state(game, 0, graveyard=[creature1, creature2], hand=[])

        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 2
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        assert creature1 in bf
        assert creature2 in bf

    def test_x_zero_returns_zero_cost_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]

        token_like = Creature(name="Zero Cost", owner=p1, base_power=1, base_toughness=1)
        token_like.card_types = {CardType.CREATURE}
        token_like.mana_cost = ManaCost.parse("{0}")  # mana value 0
        set_board_state(game, 0, graveyard=[token_like], hand=[])

        spell = FixWhatsBroken(owner=p1, controller=p1)
        spell.x_value = 0
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        assert token_like in bf
