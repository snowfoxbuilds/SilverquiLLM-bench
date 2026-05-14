"""Audited tests for FDN 193 — Drakuseth, Maw of Flames."""

from __future__ import annotations

from card_impl import DrakusethMawOfFlames
from engine.card import Creature
from engine.triggers import EventType
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestDrakusethBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = DrakusethMawOfFlames(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = DrakusethMawOfFlames(owner=None)
        assert card.name == "Drakuseth, Maw of Flames"

    def test_mana_cost(self) -> None:
        card = DrakusethMawOfFlames(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{R}{R}{R}")

    def test_power_toughness(self) -> None:
        card = DrakusethMawOfFlames(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_flying(self) -> None:
        card = DrakusethMawOfFlames(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = DrakusethMawOfFlames(owner=None)
        assert "Dragon" in card.subtypes

    def test_is_legendary(self) -> None:
        card = DrakusethMawOfFlames(owner=None)
        assert "Legendary" in getattr(card, "supertypes", set())


class TestDrakusethAttackTrigger:
    """Whenever Drakuseth attacks, deals 4 to one target and 3 to up to two others."""

    def test_deals_damage_on_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        drake = DrakusethMawOfFlames(owner=p1, controller=p1)
        game.get_battlefield(p1).add(drake)
        drake.register_triggers(game)
        # Script p1's choices: choose p2 for 4 damage, then p2 for 3, then p2 for 3
        # (DeterministicPlayer.choose_card picks from script)
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(p2)  # 4 damage target
            p1._script.append(p2)  # first 3 damage target
            p1._script.append(p2)  # second 3 damage target
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EventType.ATTACKS, {"creature": drake})
        _resolve_stack(game)
        # At minimum, 4 damage to p2
        assert p2.life <= p2_life_before - 4
