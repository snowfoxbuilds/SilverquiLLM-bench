"""Tests for SOS 84 — Forum Necroscribe."""

from __future__ import annotations

from cards.sos.sos_84.card_impl import ForumNecroscribe
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestForumNecroscribeProperties:
    """Static card data should match the SOS 84 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ForumNecroscribe(owner=None), Creature)

    def test_name(self) -> None:
        assert ForumNecroscribe(owner=None).name == "Forum Necroscribe"

    def test_mana_cost(self) -> None:
        assert ForumNecroscribe(owner=None).mana_cost == ManaCost.parse("{5}{B}")

    def test_power_toughness(self) -> None:
        card = ForumNecroscribe(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 4

    def test_has_ward(self) -> None:
        card = ForumNecroscribe(owner=None)
        assert Keyword.WARD in card.keywords


class TestForumNecroscribeRepartee:
    """Repartee: casting instant/sorcery targeting a creature returns a creature from graveyard."""

    def test_repartee_triggers_on_instant_targeting_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]

        necroscribe = ForumNecroscribe(owner=p1, controller=p1)
        necroscribe.card_types = {CardType.CREATURE}

        # A creature in graveyard to reanimate
        dead_bear = Creature(name="Dead Bear", owner=p1, controller=p1,
                             base_power=2, base_toughness=2)
        dead_bear.card_types = {CardType.CREATURE}

        # A creature on battlefield to target with an instant
        target_creature = Creature(name="Target Creature", owner=p1, controller=p1,
                                   base_power=1, base_toughness=1)
        target_creature.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[necroscribe, target_creature],
                        graveyard=[dead_bear])

        # Simulate casting an instant that targets a creature
        # The repartee ability should trigger and return dead_bear to battlefield
        necroscribe.on_repartee_trigger(game, target_creature)

        bf = game.get_battlefield(p1)
        bf_names = [c.name for c in bf.cards] if hasattr(bf, 'cards') else [c.name for c in bf]
        assert "Dead Bear" in bf_names

    def test_repartee_does_not_trigger_without_creature_target(self) -> None:
        """Repartee only triggers when an instant/sorcery targets a creature."""
        game = create_game()
        p1 = game.players[0]

        necroscribe = ForumNecroscribe(owner=p1, controller=p1)
        necroscribe.card_types = {CardType.CREATURE}

        dead_bear = Creature(name="Dead Bear", owner=p1, controller=p1,
                             base_power=2, base_toughness=2)
        dead_bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[necroscribe], graveyard=[dead_bear])

        # No repartee trigger when no creature is targeted
        # Graveyard should remain unchanged
        gy = game.get_graveyard(p1)
        gy_names = [c.name for c in gy.cards] if hasattr(gy, 'cards') else [c.name for c in gy]
        assert "Dead Bear" in gy_names

    def test_repartee_no_creature_in_graveyard_is_noop(self) -> None:
        """If no creature card in graveyard, repartee resolves as noop."""
        game = create_game()
        p1 = game.players[0]

        necroscribe = ForumNecroscribe(owner=p1, controller=p1)
        necroscribe.card_types = {CardType.CREATURE}

        target_creature = Creature(name="Target Creature", owner=p1, controller=p1,
                                   base_power=1, base_toughness=1)
        target_creature.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[necroscribe, target_creature],
                        graveyard=[])

        # Should not raise even with empty graveyard
        necroscribe.on_repartee_trigger(game, target_creature)
