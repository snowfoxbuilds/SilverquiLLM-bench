"""Audited tests for FDN 257 — Solemn Simulacrum."""

from __future__ import annotations

from card_impl import SolemnSimulacrum
from engine.card import ArtifactCreature, CardImpl
from engine.types import CardType, ManaCost, Supertype, Zone
from engine.triggers import EventType
from tests.test_utils import create_game


class TestSolemnSimulacrumBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = SolemnSimulacrum(owner=None)
        assert card.name == "Solemn Simulacrum"

    def test_mana_cost(self) -> None:
        card = SolemnSimulacrum(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}")

    def test_power_toughness(self) -> None:
        card = SolemnSimulacrum(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_is_artifact_creature(self) -> None:
        card = SolemnSimulacrum(owner=None)
        assert isinstance(card, ArtifactCreature)

    def test_golem_subtype(self) -> None:
        card = SolemnSimulacrum(owner=None)
        assert "Golem" in card.subtypes


class TestSolemnSimulacrumETB:
    """When enters, search library for basic land, put onto battlefield tapped."""

    def test_etb_fetches_basic_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sim = SolemnSimulacrum(owner=p1, controller=p1)
        game.get_battlefield(p1).add(sim)

        # Put a basic land in library
        basic = CardImpl(name="Plains", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        basic.card_types = {CardType.LAND}
        basic.supertypes = {Supertype.BASIC}
        p1.zones[Zone.LIBRARY].add(basic)

        sim.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": sim},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        assert basic in bf
        assert basic.is_tapped is True

    def test_etb_no_land_if_library_empty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sim = SolemnSimulacrum(owner=p1, controller=p1)
        game.get_battlefield(p1).add(sim)
        sim.register_triggers(game)

        bf_before = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": sim},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after == bf_before

    def test_etb_shuffles_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sim = SolemnSimulacrum(owner=p1, controller=p1)
        game.get_battlefield(p1).add(sim)

        # Add basic land and some filler to library
        basic = CardImpl(name="Plains", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        basic.card_types = {CardType.LAND}
        basic.supertypes = {Supertype.BASIC}
        p1.zones[Zone.LIBRARY].add(basic)
        for i in range(5):
            filler = CardImpl(name=f"Card{i}", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
            p1.zones[Zone.LIBRARY].add(filler)

        sim.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": sim},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        # Basic should be on battlefield, library should still have cards
        assert basic in game.get_battlefield(p1).get_all()
        assert len(p1.zones[Zone.LIBRARY]) == 5


class TestSolemnSimulacrumDeath:
    """When this creature dies, you may draw a card."""

    def test_draws_card_on_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sim = SolemnSimulacrum(owner=p1, controller=p1)
        game.get_battlefield(p1).add(sim)

        # Put a card in library to draw
        card_in_lib = CardImpl(name="Spell", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(card_in_lib)

        sim.register_triggers(game)

        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(
            game,
            EventType.CREATURE_DIES,
            {"creature": sim},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before + 1

    def test_no_draw_for_other_creature_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sim = SolemnSimulacrum(owner=p1, controller=p1)
        game.get_battlefield(p1).add(sim)

        card_in_lib = CardImpl(name="Spell", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(card_in_lib)

        sim.register_triggers(game)

        from engine.card import Creature
        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)

        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(
            game,
            EventType.CREATURE_DIES,
            {"creature": other},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before

