"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Sorcery
from engine.casting import cast_spell as engine_cast
from engine.types import Keyword, ManaCost, ManaType, Phase, Supertype
from test_utils import create_game, set_board_state


class _DamageSorcery(Sorcery):
    """Test sorcery that deals 2 damage to its controller's opponent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        controller = self.controller
        opp = game.players[1] if controller is game.players[0] else game.players[0]
        deal_damage(game, self, opp, 2)


def _resolve_all(game) -> None:
    """Resolve the entire stack without granting priority (no scripted passes)."""
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _sorcery_timing(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestSilverquillProperties:
    def test_name_and_stats(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_keywords_and_types(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestSilverquillCasualty:
    def test_casualty_copies_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        zap = _DamageSorcery(owner=p1, controller=p1)
        set_board_state(
            game, 0, battlefield=[silver, fodder], hand=[zap], mana={ManaType.RED: 1}
        )
        silver.register_triggers(game)

        # Casualty resolution will ask: yes, then which creature.
        p1._script.append(True)
        p1._script.append(fodder)

        _sorcery_timing(game)
        engine_cast(game, p1, zap)
        _resolve_all(game)

        # Original + copy each deal 2 → 4 total; fodder sacrificed.
        assert p2.life == 20 - 4
        assert fodder in game.get_graveyard(p1).get_all()
        assert fodder not in game.get_battlefield(p1).get_all()

    def test_decline_casualty_no_copy(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        zap = _DamageSorcery(owner=p1, controller=p1)
        set_board_state(
            game, 0, battlefield=[silver, fodder], hand=[zap], mana={ManaType.RED: 1}
        )
        silver.register_triggers(game)

        p1._script.append(False)  # decline casualty

        _sorcery_timing(game)
        engine_cast(game, p1, zap)
        _resolve_all(game)

        assert p2.life == 20 - 2
        assert fodder in game.get_battlefield(p1).get_all()

    def test_opponent_spell_does_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        zap = _DamageSorcery(owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[silver])
        set_board_state(game, 1, hand=[zap], mana={ManaType.RED: 1})
        silver.register_triggers(game)

        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        engine_cast(game, p2, zap)

        # No casualty trigger should be on the stack (only the spell itself).
        assert len(game.stack) == 1
