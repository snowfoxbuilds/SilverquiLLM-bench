"""Tests for SOS 132 — Tablet of Discovery."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_132.card_impl import TabletOfDiscovery
from benchmarks.sos.workspace.engine.card import Artifact, CardImpl, Creature, Land, ManaAbility, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, play_land
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, Step, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestTabletOfDiscoveryProperties:
    """Static card data should match the SOS 132 spec."""

    def test_is_artifact(self) -> None:
        assert isinstance(TabletOfDiscovery(owner=None), Artifact)

    def test_name_and_mana_cost(self) -> None:
        card = TabletOfDiscovery(owner=None)

        assert card.name == "Tablet of Discovery"
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestTabletOfDiscoveryEnters:
    """Tablet of Discovery should mill and use the milled card."""

    def test_on_resolve_mills_the_top_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)

        card = TabletOfDiscovery(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_graveyard(p1).contains(top)
        assert not game.get_library(p1).contains(top)
        assert game.get_library(p1).contains(bottom)


class TestTabletOfDiscoveryGraveyardPlayPermission:
    """Tablet of Discovery should let its controller play the milled card this turn."""

    def test_on_resolve_grants_controller_only_graveyard_play_permission_for_milled_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = Sorcery(
            name="Lecture in Flame",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{R}"),
        )
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)

        card = TabletOfDiscovery(owner=p1, controller=p1)
        card.on_resolve(game)

        permissions = game.get_graveyard_play_permissions(player=p1)

        assert game.can_player_play_graveyard_card(p1, top) is True
        assert game.can_player_play_graveyard_card(p1, bottom) is False
        assert game.can_player_play_graveyard_card(p2, top) is False
        assert len(permissions) == 1
        assert permissions[0].card is top
        assert permissions[0].source is card

    def test_milled_sorcery_can_be_cast_from_graveyard_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = Sorcery(
            name="Lecture in Flame",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{R}"),
        )
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)

        card = TabletOfDiscovery(owner=p1, controller=p1)
        card.on_resolve(game)
        p1.mana_pool.add(ManaType.RED, 1)

        cast_spell_paid(game, p1, top, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is top
        assert not game.get_graveyard(p1).contains(top)
        assert game.can_player_play_graveyard_card(p1, top) is False

    def test_milled_land_can_be_played_from_graveyard_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = Land(name="Surveyed Crag", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)

        card = TabletOfDiscovery(owner=p1, controller=p1)
        card.on_resolve(game)

        play_land(game, p1, top)

        assert game.get_battlefield(p1).contains(top)
        assert not game.get_graveyard(p1).contains(top)
        assert p1.land_plays_remaining == 0
        assert game.can_player_play_graveyard_card(p1, top) is False

    def test_milled_card_play_permission_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        top = Sorcery(
            name="Lecture in Flame",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{R}"),
        )
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(top)

        card = TabletOfDiscovery(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.can_player_play_graveyard_card(p1, top) is True

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.can_player_play_graveyard_card(p1, top) is False
        assert game.get_graveyard_play_permissions(player=p1) == []


class TestTabletOfDiscoveryManaAbilities:
    """Tablet of Discovery should provide two red mana abilities."""

    def test_has_two_mana_abilities(self) -> None:
        abilities = TabletOfDiscovery(owner=None).get_mana_abilities()

        assert len(abilities) == 2
        assert all(isinstance(ability, ManaAbility) for ability in abilities)

    def test_first_mana_ability_taps_to_add_red_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TabletOfDiscovery(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[0]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True

        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.RED) == 1

    def test_second_mana_ability_taps_to_add_two_red_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TabletOfDiscovery(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_mana_abilities()[1]

        assert ability.cost(game, card) is True
        assert card.is_tapped is True

        ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.RED) == 2

    def test_second_mana_ability_mana_cannot_be_spent_on_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TabletOfDiscovery(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Practice Performer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{R}{R}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card], hand=[creature_spell])
        ability = card.get_mana_abilities()[1]

        assert ability.cost(game, card) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.RED) == 2

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, creature_spell)

        assert game.get_hand(p1).contains(creature_spell)
        assert p1.mana_pool.get(ManaType.RED) == 2

    def test_second_mana_ability_mana_can_be_spent_on_a_sorcery_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = TabletOfDiscovery(owner=p1, controller=p1)
        sorcery_spell = Sorcery(
            name="Lecture in Flame",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{R}{R}"),
        )
        set_board_state(game, 0, battlefield=[card], hand=[sorcery_spell])
        ability = card.get_mana_abilities()[1]

        assert ability.cost(game, card) is True
        ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.RED) == 2

        cast_spell_paid(game, p1, sorcery_spell)

        assert game.stack.peek().source is sorcery_spell
        assert p1.mana_pool.total() == 0
