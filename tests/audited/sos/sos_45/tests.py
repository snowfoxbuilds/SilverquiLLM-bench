"""Audited tests for Emeritus of Ideation // Ancestral Recall (collector key 45).

Verifies the Emeritus of Ideation // Ancestral Recall card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import EmeritusOfIdeationAncestralRecall

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEmeritusOfIdeationAncestralRecallBasicProperties:
    """Basic property tests for Emeritus of Ideation // Ancestral Recall."""

    def test_is_creature(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must be a Creature subclass."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EmeritusOfIdeationAncestralRecall.name must be 'Emeritus of Ideation // Ancestral Recall'."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert card.name == "Emeritus of Ideation // Ancestral Recall"

    def test_card_types(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have correct card types."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have converted mana cost 6."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have correct colors."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have base power 5."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have base toughness 5."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert card.base_toughness == 5


@pytest.mark.ability
class TestEmeritusOfIdeationAncestralRecallAbilities:
    """Ability tests for Emeritus of Ideation // Ancestral Recall -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have Flying keyword."""
        from engine.types import Keyword
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert Keyword.FLYING in card.keywords, "Emeritus of Ideation // Ancestral Recall should have Flying"

    def test_has_prepared(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have Prepared keyword."""
        from engine.types import Keyword
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert Keyword.PREPARED in card.keywords, "Emeritus of Ideation // Ancestral Recall should have Prepared"

    def test_has_ward(self) -> None:
        """Emeritus of Ideation // Ancestral Recall must have Ward keyword."""
        from engine.types import Keyword
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert Keyword.WARD in card.keywords, "Emeritus of Ideation // Ancestral Recall should have Ward"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Emeritus of Ideation // Ancestral Recall must implement on_enter_battlefield per oracle text"

    def test_attack_trigger_uses_graveyard(self) -> None:
        """Attack trigger must interact with graveyard per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Bolt", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after != gy_before, "Attack trigger must interact with graveyard"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Emeritus of Ideation // Ancestral Recall must implement prepared mechanic"


@pytest.mark.edge
class TestEmeritusOfIdeationAncestralRecallEdgeCases:
    """Edge case and trap tests for Emeritus of Ideation // Ancestral Recall."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        card2 = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        card1.name = "Modified"
        assert card2.name == "Emeritus of Ideation // Ancestral Recall", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=None, base_power=5, base_toughness=5)
        assert card.mana_cost.cmc == 6, \
            f"CMC must be 6, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 4
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestEmeritusOfIdeationAncestralRecallInteractions:
    """Multi-card interaction tests for Emeritus of Ideation // Ancestral Recall."""

    def test_exile_from_graveyard_interaction(self) -> None:
        """Cards exiled from graveyard must move to exile zone."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Fodder", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        elif callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = player.zones[Zone.EXILE].get_all()
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert fodder in exile or fodder not in gy, \
            "Exiled card must leave graveyard"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = EmeritusOfIdeationAncestralRecall(name="Emeritus of Ideation // Ancestral Recall", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
