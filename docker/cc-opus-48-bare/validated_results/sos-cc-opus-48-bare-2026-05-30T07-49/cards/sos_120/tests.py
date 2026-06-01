"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Phase, Zone
from test_utils import create_game, set_board_state


class _DamageInstant(Instant):
    """Test instant (mana value 4) that deals 2 damage to the opponent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        controller = self.controller
        opp = game.players[1] if controller is game.players[0] else game.players[0]
        deal_damage(game, self, opp, 2)


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _add_to_library(game, player, card) -> None:
    card.owner = player
    card.controller = player
    game.get_library(player).add(card)


def _cmc2(name: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{R}"))


class TestCapstoneProperties:
    def test_name_and_type(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes


class TestCapstoneExile:
    def test_exiles_top_until_total_mv_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        bottom = _cmc2("bottom")
        mid = _cmc2("mid")
        top = _cmc2("top")
        for c in (bottom, mid, top):  # 'top' ends up on top of library
            _add_to_library(game, p1, c)

        # Two cmc-2 cards (top, mid) reach total mv 4 — stop there.
        p1._script.append(False)
        p1._script.append(False)
        cap.on_resolve(game)

        exiled = game.get_exile(p1).get_all()
        assert top in exiled and mid in exiled
        assert bottom in game.get_library(p1).get_all()
        assert len(exiled) == 2
        # Paradigm flag set so the resolution pipeline exiles the spell.
        assert cap._exile_instead_of_graveyard is True

    def test_zero_mv_lands_are_exiled_but_not_castable(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        big = _DamageInstant(name="Big")  # mv 4
        land = Land(name="Wastes")
        # Library top-to-bottom: land, then big. Land (mv 0) doesn't satisfy
        # the threshold, so 'big' is exiled too.
        _add_to_library(game, p1, big)
        _add_to_library(game, p1, land)

        p1._script.append(False)  # decline casting 'big' (land isn't castable)
        cap.on_resolve(game)

        exiled = game.get_exile(p1).get_all()
        assert land in exiled
        assert big in exiled

    def test_stops_when_library_empties(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        only = _cmc2("only")  # mv 2 < 4, but library runs out
        _add_to_library(game, p1, only)

        p1._script.append(False)
        cap.on_resolve(game)

        assert only in game.get_exile(p1).get_all()
        assert len(game.get_library(p1).get_all()) == 0


class TestCapstoneFreeCast:
    def test_casts_chosen_spell_for_free(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        zap = _DamageInstant(owner=p1, controller=p1)  # mv 4
        _add_to_library(game, p1, zap)
        set_board_state(game, 1, life=20)

        p1._script.append(True)  # cast it without paying
        cap.on_resolve(game)
        _resolve_all(game)

        assert p2.life == 18
        assert zap in game.get_graveyard(p1).get_all()
        assert zap not in game.get_exile(p1).get_all()


class TestParadigm:
    def _exiled_capstone(self, game, p1):
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        game.get_exile(p1).add(cap)
        return cap

    def test_recurs_on_first_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = self._exiled_capstone(game, p1)
        big = _DamageInstant(name="Big")  # mv 4
        _add_to_library(game, p1, big)
        cap._register_paradigm(game, p1)

        p1._script.append(True)   # yes, cast a copy
        p1._script.append(False)  # decline casting the exiled card
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN, player=p1),
        )
        _resolve_all(game)

        assert len(game.get_library(p1).get_all()) == 0
        assert big in game.get_exile(p1).get_all()

    def test_does_not_recur_on_postcombat_main(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = self._exiled_capstone(game, p1)
        _add_to_library(game, p1, _cmc2("c"))
        cap._register_paradigm(game, p1)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(phase=Phase.POSTCOMBAT_MAIN, player=p1),
        )
        assert game.stack.is_empty()
        assert len(game.get_library(p1).get_all()) == 1

    def test_does_not_recur_on_opponents_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cap = self._exiled_capstone(game, p1)
        _add_to_library(game, p1, _cmc2("c"))
        cap._register_paradigm(game, p1)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN, player=p2),
        )
        assert game.stack.is_empty()
        assert len(game.get_library(p1).get_all()) == 1

    def test_does_not_recur_when_not_in_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Capstone is NOT in exile (e.g. it never resolved with Paradigm).
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        _add_to_library(game, p1, _cmc2("c"))
        cap._register_paradigm(game, p1)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN, player=p1),
        )
        assert game.stack.is_empty()
