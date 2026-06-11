"""Tests for SOS 112 — Duel Tactics."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_112.card_impl import DuelTactics
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestDuelTacticsProperties:
    """Static card data should match the SOS 112 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(DuelTactics(owner=None), Sorcery)

    def test_name_cost_and_flashback_cost(self) -> None:
        card = DuelTactics(owner=None)
        assert card.name == "Duel Tactics"
        assert card.mana_cost == ManaCost.parse("{R}")
        assert card.flashback_cost == ManaCost.parse("{1}{R}")


class TestDuelTacticsTargeting:
    """Duel Tactics should target a creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = DuelTactics(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = DuelTactics(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestDuelTacticsResolution:
    """Duel Tactics should deal damage and stop the target from blocking this turn."""

    def test_deals_one_damage_and_target_cannot_block_this_turn(self) -> None:
        game = create_game()
        p2 = game.players[1]
        target = Creature(
            name="Defender",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(target)

        card = DuelTactics(owner=game.players[0], controller=game.players[0])
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert target.damage_marked == 1
        assert target._cant_block is True

    def test_cannot_block_effect_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p2 = game.players[1]
        target = Creature(
            name="Temporary Blocker",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=3,
        )
        game.get_battlefield(p2).add(target)

        card = DuelTactics(owner=game.players[0], controller=game.players[0])
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target._cant_block is True

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target._cant_block is False

    def test_paid_flashback_cast_from_graveyard_exiles_on_resolution(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        target = Creature(
            name="Defender",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = DuelTactics(owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_graveyard(p1).add(spell)
        p1.mana_pool.add(ManaType.RED, 2)
        p1._script.append(target)

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert target.damage_marked == 1
        assert target._cant_block is True
