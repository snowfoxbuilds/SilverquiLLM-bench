"""Tests for SOS 30 — Restoration Seminar."""

from __future__ import annotations

import pytest
from cards.sos.sos_30.card_impl import RestorationSeminar
from engine.card import Creature, Sorcery, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone, TargetRequirement
from test_utils import create_game, set_board_state, cast_spell, advance_to_phase


class TestRestorationSeminarProperties:
    """Static card data should match the SOS 30 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(RestorationSeminar(owner=None), Sorcery)

    def test_name(self) -> None:
        assert RestorationSeminar(owner=None).name == "Restoration Seminar"

    def test_mana_cost(self) -> None:
        assert RestorationSeminar(owner=None).mana_cost == ManaCost.parse("{5}{W}{W}")


class TestRestorationSeminarTargeting:
    """Return target nonland permanent card from your graveyard to the battlefield."""

    def test_targets_graveyard(self) -> None:
        game = create_game()
        spell = RestorationSeminar(owner=None)
        reqs = spell.get_targets(game)
        assert len(reqs) >= 1
        assert reqs[0].zone == Zone.GRAVEYARD

    def test_target_filter_accepts_nonland_permanent(self) -> None:
        game = create_game()
        spell = RestorationSeminar(owner=None)
        req = spell.get_targets(game)[0]
        creature = Creature(name="Angel", base_power=4, base_toughness=4)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True

    def test_target_filter_rejects_land(self) -> None:
        game = create_game()
        spell = RestorationSeminar(owner=None)
        req = spell.get_targets(game)[0]
        from engine.card import CardImpl
        land = CardImpl(name="Plains")
        land.card_types = {CardType.LAND}
        assert req.filter_fn(land) is False

    def test_no_mana_value_restriction(self) -> None:
        """Unlike Primary Research, this has no MV restriction."""
        game = create_game()
        spell = RestorationSeminar(owner=None)
        req = spell.get_targets(game)[0]
        big = Creature(name="Big Angel", base_power=7, base_toughness=7)
        big.card_types = {CardType.CREATURE}
        big.mana_cost = ManaCost.parse("{5}{W}{W}")  # MV = 7
        assert req.filter_fn(big) is True


class TestRestorationSeminarResolution:
    """Returns the permanent and exiles itself (Paradigm)."""

    def test_returns_creature_from_graveyard_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        angel = Creature(name="Angel", owner=p1, controller=p1, base_power=4, base_toughness=4)
        angel.card_types = {CardType.CREATURE}
        set_board_state(game, 0, graveyard=[angel], hand=[RestorationSeminar(owner=p1)],
                        mana={ManaType.WHITE: 7, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Restoration Seminar", targets=[angel])
        bf = game.get_battlefield(p1)
        assert angel in bf

    def test_spell_exiles_itself_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        angel = Creature(name="Angel", owner=p1, controller=p1, base_power=4, base_toughness=4)
        angel.card_types = {CardType.CREATURE}
        spell = RestorationSeminar(owner=p1)
        set_board_state(game, 0, graveyard=[angel], hand=[spell],
                        mana={ManaType.WHITE: 7, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Restoration Seminar", targets=[angel])
        # Spell should be in exile, not graveyard
        exile = game.get_exile(p1)
        gy = game.get_graveyard(p1)
        assert spell in exile or any(c.name == "Restoration Seminar" for c in exile)


class TestRestorationSeminarParadigm:
    """Paradigm — After first resolve, cast a free copy at beginning of first main phases."""

    def test_paradigm_provides_free_copy_on_subsequent_turns(self) -> None:
        game = create_game()
        p1 = game.players[0]
        angel = Creature(name="Angel", owner=p1, controller=p1, base_power=4, base_toughness=4)
        angel.card_types = {CardType.CREATURE}
        spell = RestorationSeminar(owner=p1)
        set_board_state(game, 0, graveyard=[angel], hand=[spell],
                        mana={ManaType.WHITE: 7, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Restoration Seminar", targets=[angel])
        # On next turn's first main phase, should get a free copy trigger
        dragon = Creature(name="Dragon", owner=p1, controller=p1, base_power=5, base_toughness=5)
        dragon.card_types = {CardType.CREATURE}
        set_board_state(game, 0, graveyard=[dragon])
        # Advance to next turn's precombat main
        game.next_turn()
        from engine.types import Phase
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        # The paradigm trigger should allow casting a free copy
        assert game.paradigm_trigger_available(p1, "Restoration Seminar") is True
