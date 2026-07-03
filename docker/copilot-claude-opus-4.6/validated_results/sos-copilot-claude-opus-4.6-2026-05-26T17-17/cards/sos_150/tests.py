"""Tests for SOS 150 — Glorious Decay."""

from __future__ import annotations

import pytest

from cards.sos.sos_150.card_impl import GloriousDecay
from engine.card import Creature, Instant, Artifact
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestGloriousDecayProperties:
    """Static card data should match the SOS 150 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(GloriousDecay(owner=None), Instant)

    def test_name(self) -> None:
        assert GloriousDecay(owner=None).name == "Glorious Decay"

    def test_mana_cost(self) -> None:
        assert GloriousDecay(owner=None).mana_cost == ManaCost.parse("{1}{G}")


class TestGloriousDecayModes:
    """Modal spell with three modes."""

    def test_has_three_modes(self) -> None:
        card = GloriousDecay(owner=None)
        assert len(card.modes) == 3


class TestGloriousDecayMode1:
    """Mode 1: Destroy target artifact."""

    def test_destroys_artifact(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        from engine.card import Artifact
        artifact = Artifact(name="Sol Ring", owner=p2, controller=p2)
        artifact.card_types = {CardType.ARTIFACT}
        game.get_battlefield(p2).add(artifact)
        spell = GloriousDecay(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.chosen_targets = [artifact]
        spell.on_resolve(game)
        battlefield = game.get_battlefield(p2)
        assert not any(c.name == "Sol Ring" for c in battlefield)

    def test_mode1_target_must_be_artifact(self) -> None:
        """Non-artifact should not be a valid target for mode 1."""
        game = create_game()
        p1 = game.players[0]
        card = GloriousDecay(owner=p1, controller=p1)
        card.chosen_mode = 0
        reqs = card.get_targets(game)
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert reqs[0].filter_fn(creature) is False


class TestGloriousDecayMode2:
    """Mode 2: Deal 4 damage to target creature with flying."""

    def test_deals_4_damage_to_flyer(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        flyer = Creature(name="Bird", owner=p2, controller=p2,
                         base_power=2, base_toughness=5)
        flyer.card_types = {CardType.CREATURE}
        flyer.keywords = Keyword.FLYING
        game.get_battlefield(p2).add(flyer)
        spell = GloriousDecay(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [flyer]
        spell.on_resolve(game)
        assert flyer.damage_taken == 4

    def test_mode2_target_must_have_flying(self) -> None:
        """A creature without flying is not a valid target for mode 2."""
        game = create_game()
        p1 = game.players[0]
        card = GloriousDecay(owner=p1, controller=p1)
        card.chosen_mode = 1
        reqs = card.get_targets(game)
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        creature.keywords = Keyword(0)
        assert reqs[0].filter_fn(creature) is False

    def test_mode2_kills_small_flyer(self) -> None:
        """4 damage should kill a 2/2 flyer."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        flyer = Creature(name="Bird", owner=p2, controller=p2,
                         base_power=2, base_toughness=2)
        flyer.card_types = {CardType.CREATURE}
        flyer.keywords = Keyword.FLYING
        game.get_battlefield(p2).add(flyer)
        spell = GloriousDecay(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [flyer]
        spell.on_resolve(game)
        # Bird should be dead (moved to graveyard)
        bf = game.get_battlefield(p2)
        assert not any(c.name == "Bird" for c in bf)


class TestGloriousDecayMode3:
    """Mode 3: Exile target card from a graveyard. Draw a card."""

    def test_exiles_card_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        dead_bear = Creature(name="Dead Bear", owner=p2,
                             base_power=2, base_toughness=2)
        game.get_graveyard(p2).append(dead_bear)
        spell = GloriousDecay(owner=p1, controller=p1)
        spell.chosen_mode = 2
        spell.chosen_targets = [dead_bear]
        spell.on_resolve(game)
        gy = game.get_graveyard(p2)
        assert not any(c.name == "Dead Bear" for c in gy)

    def test_mode3_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        dead_bear = Creature(name="Dead Bear", owner=p2,
                             base_power=2, base_toughness=2)
        game.get_graveyard(p2).append(dead_bear)
        # Put a card in library to draw
        from engine.card import Sorcery
        top_card = Sorcery(name="TopCard", owner=p1)
        game.get_library(p1).append(top_card)
        hand_before = len(game.get_hand(p1))
        spell = GloriousDecay(owner=p1, controller=p1)
        spell.chosen_mode = 2
        spell.chosen_targets = [dead_bear]
        spell.on_resolve(game)
        hand_after = len(game.get_hand(p1))
        assert hand_after == hand_before + 1
