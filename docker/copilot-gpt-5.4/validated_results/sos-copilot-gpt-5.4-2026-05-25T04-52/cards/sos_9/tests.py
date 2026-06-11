"""Tests for SOS 9 — Daydream."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_9.card_impl import Daydream
from benchmarks.sos.workspace.engine.casting import (
    CastingError,
    cast_spell as cast_spell_paid,
    cast_spell_free,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestDaydreamProperties:
    """Static card data should match the SOS 9 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(Daydream(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = Daydream(owner=None)
        assert card.name == "Daydream"
        assert card.mana_cost == ManaCost.parse("{W}")


class TestDaydreamTargeting:
    """The spell should only target a creature you control on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = Daydream(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_your_creature_and_rejects_opponents_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = Daydream(owner=p1, controller=p1).get_targets(game)[0]

        your_creature = Creature(
            name="My Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponent_creature = Creature(
            name="Enemy Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        assert req.filter_fn(your_creature) is True
        assert req.filter_fn(opponent_creature) is False


class TestDaydreamResolution:
    """Daydream should blink the target and return it with a counter."""

    def test_returns_the_target_under_its_owners_control_with_a_counter(self) -> None:
        game = create_game()
        p1, p2 = game.players
        stolen = Creature(
            name="Borrowed Bear",
            owner=p2,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(stolen)

        card = Daydream(owner=p1, controller=p1)
        card.chosen_targets = [stolen]
        card.on_resolve(game)

        assert not game.get_battlefield(p1).contains(stolen)
        assert game.get_battlefield(p2).contains(stolen)
        assert stolen.controller is p2
        assert stolen.plus_one_counters == 1
        assert not game.get_exile(p2).contains(stolen)

    def test_graveyard_cast_uses_flashback_style_exile_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Friendly Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = Daydream(owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        game.get_graveyard(p1).add(spell)
        p1._script.append(target)

        cast_spell_free(game, p1, spell, Zone.GRAVEYARD, exile_on_resolve=True)
        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert game.get_battlefield(p1).contains(target)
        assert target.plus_one_counters == 1

    def test_paid_flashback_cast_from_graveyard_requires_two_and_white(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        target = Creature(
            name="Dreaming Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = Daydream(owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        game.get_graveyard(p1).add(spell)
        p1.mana_pool.add(ManaType.WHITE, 1)
        p1._script.append(target)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.get(ManaType.WHITE) == 1

    def test_paid_flashback_cast_from_graveyard_exiles_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        target = Creature(
            name="Dreaming Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = Daydream(owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        game.get_graveyard(p1).add(spell)
        p1.mana_pool.add(ManaType.WHITE, 3)
        p1._script.append(target)

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.total() == 0

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert game.get_battlefield(p1).contains(target)
        assert target.plus_one_counters == 1
