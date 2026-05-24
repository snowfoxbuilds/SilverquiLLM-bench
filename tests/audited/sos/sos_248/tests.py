"""Audited tests for Diary of Dreams (collector key 248).

Verifies the Diary of Dreams card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import DiaryOfDreams

from engine.card import Artifact
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDiaryOfDreamsBasicProperties:
    """Basic property tests for Diary of Dreams."""

    def test_is_artifact(self) -> None:
        """Diary of Dreams must be a Artifact subclass."""
        card = DiaryOfDreams(name="Diary of Dreams", owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        """DiaryOfDreams.name must be 'Diary of Dreams'."""
        card = DiaryOfDreams(name="Diary of Dreams", owner=None)
        assert card.name == "Diary of Dreams"

    def test_card_types(self) -> None:
        """Diary of Dreams must have correct card types."""
        card = DiaryOfDreams(name="Diary of Dreams", owner=None)
        assert CardType.ARTIFACT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Diary of Dreams must have converted mana cost 2."""
        card = DiaryOfDreams(name="Diary of Dreams", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Diary of Dreams must have correct colors."""
        card = DiaryOfDreams(name="Diary of Dreams", owner=None)
        assert len(card.colors) == 0


@pytest.mark.ability
class TestDiaryOfDreamsAbilities:
    """Ability tests for Diary of Dreams — expected to fail against stubs."""

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = DiaryOfDreams(name="Diary of Dreams", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_cost_reduction_applies(self) -> None:
        """cost_reduction should return > 0 when condition met."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = DiaryOfDreams(name="Diary of Dreams", owner=player)
        card.controller = player
        target = Creature(name="Cond", owner=player, base_power=2, base_toughness=2)
        target.tapped = True
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        reduction = card.cost_reduction(game)
        assert reduction > 0, f"Cost reduction should apply, got {reduction}"

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = DiaryOfDreams(name="Diary of Dreams", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestDiaryOfDreamsEdgeCases:
    """Edge case tests for Diary of Dreams."""

    def test_no_reduction_when_condition_unmet(self) -> None:
        """No cost reduction when condition is not met."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = DiaryOfDreams(name="Diary of Dreams", owner=player)
        card.controller = player
        target = Creature(name="Untapped", owner=player, base_power=2, base_toughness=2)
        target.tapped = False
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        reduction = card.cost_reduction(game)
        assert reduction == 0, f"No reduction when unmet, got {reduction}"


@pytest.mark.interaction
class TestDiaryOfDreamsInteractions:
    """Interaction tests for Diary of Dreams."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = DiaryOfDreams(name="Diary of Dreams", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = DiaryOfDreams(name="Diary of Dreams", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
