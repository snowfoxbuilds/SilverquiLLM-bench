"""Tests for SOS 204 — Molten Note."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_204.card_impl import MoltenNote
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestMoltenNoteProperties:
    """Static card data should match the SOS 204 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(MoltenNote(owner=None), Sorcery)

    def test_name_cost_and_flashback_cost(self) -> None:
        card = MoltenNote(owner=None)

        assert card.name == "Molten Note"
        assert card.mana_cost == ManaCost.parse("{X}{R}{W}")
        assert card.flashback_cost == ManaCost.parse("{6}{R}{W}")


class TestMoltenNoteTargeting:
    """Molten Note should target a creature on the battlefield."""

    def test_returns_a_single_creature_target_requirement(self) -> None:
        game = create_game()
        reqs = MoltenNote(owner=game.players[0], controller=game.players[0]).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = MoltenNote(owner=game.players[0], controller=game.players[0]).get_targets(game)[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)

        assert req.filter_fn(creature) is True
        assert req.filter_fn(CardImpl(name="Lecture Notes")) is False


class TestMoltenNoteResolution:
    """Molten Note should scale with mana spent, untap your team, and support flashback."""

    def test_deals_damage_equal_to_mana_spent_and_untaps_all_creatures_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(name="Opponent Bear", owner=p2, controller=p2, base_power=5, base_toughness=5)
        your_a = Creature(name="Student A", owner=p1, controller=p1, base_power=2, base_toughness=2)
        your_b = Creature(name="Student B", owner=p1, controller=p1, base_power=2, base_toughness=2)
        opposing_other = Creature(name="Opponent Student", owner=p2, controller=p2, base_power=2, base_toughness=2)
        your_a.is_tapped = True
        your_b.is_tapped = True
        opposing_other.is_tapped = True

        set_board_state(game, 0, battlefield=[your_a, your_b])
        set_board_state(game, 1, battlefield=[target, opposing_other])

        spell = MoltenNote(owner=p1, controller=p1)
        spell.mana_spent = 5  # type: ignore[attr-defined]
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 5
        assert your_a.is_tapped is False
        assert your_b.is_tapped is False
        assert opposing_other.is_tapped is True

    def test_paid_flashback_cast_from_graveyard_exiles_on_resolution_and_uses_flashback_mana_spent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        target = Creature(name="Opponent Bear", owner=p2, controller=p2, base_power=8, base_toughness=8)
        your_creature = Creature(name="Tired Student", owner=p1, controller=p1, base_power=2, base_toughness=2)
        your_creature.is_tapped = True
        spell = MoltenNote(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[your_creature],
            graveyard=[spell],
            mana={
                ManaType.COLORLESS: 6,
                ManaType.RED: 1,
                ManaType.WHITE: 1,
            },
        )
        set_board_state(game, 1, battlefield=[target])
        p1._script.append(target)

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

        resolve_top(game)

        assert target.damage_marked == 8
        assert your_creature.is_tapped is False
        assert game.get_exile(p1).contains(spell)
