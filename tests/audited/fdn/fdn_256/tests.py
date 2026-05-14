"""Audited tests for FDN 256 — Meteor Golem."""

from __future__ import annotations

from card_impl import MeteorGolem
from engine.card import ArtifactCreature, CardImpl
from engine.types import CardType, ManaCost, Zone
from engine.triggers import EventType
from tests.test_utils import create_game


class TestMeteorGolemBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = MeteorGolem(owner=None)
        assert card.name == "Meteor Golem"

    def test_mana_cost(self) -> None:
        card = MeteorGolem(owner=None)
        assert card.mana_cost == ManaCost.parse("{7}")

    def test_power_toughness(self) -> None:
        card = MeteorGolem(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_is_artifact_creature(self) -> None:
        card = MeteorGolem(owner=None)
        assert isinstance(card, ArtifactCreature)

    def test_golem_subtype(self) -> None:
        card = MeteorGolem(owner=None)
        assert "Golem" in card.subtypes


class TestMeteorGolemETB:
    """When this creature enters, destroy target nonland permanent."""

    def test_destroys_target_on_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        golem = MeteorGolem(owner=p1, controller=p1)
        game.get_battlefield(p1).add(golem)

        # Opponent's nonland permanent
        target = CardImpl(name="Enchantment", mana_cost=ManaCost(generic=0), owner=p2, controller=p2)
        target.card_types = {CardType.ENCHANTMENT}
        game.get_battlefield(p2).add(target)

        # Set chosen target
        golem.chosen_targets = [target]
        golem.register_triggers(game)

        # Fire ETB
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": golem},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Target should be destroyed (removed from battlefield)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf

    def test_no_effect_if_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        golem = MeteorGolem(owner=p1, controller=p1)
        game.get_battlefield(p1).add(golem)
        golem.register_triggers(game)

        # Fire ETB with no target set — should not crash
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": golem},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

