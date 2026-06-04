"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class _GainLife(Sorcery):
    """A no-target sorcery: gain 3 life on resolve. Printed cost {4}{R} (MV 5)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Recollect")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


def _spell(name="Spell", cost="{4}{R}"):
    return _GainLife(name=name, mana_cost=ManaCost.parse(cost))


def _creature(name="Bear", cost="{1}{G}"):
    return Creature(
        name=name, base_power=2, base_toughness=2, mana_cost=ManaCost.parse(cost)
    )


def _land(name="Forest"):
    return Land(name=name)


def _set_library(game, player, top_to_bottom):
    """Place *top_to_bottom* in the library; index 0 ends up on top."""
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in reversed(top_to_bottom):
        c.owner = player
        c.controller = player
        lib.add(c)


def _cast_capstone(game, library, answers):
    """Put a Capstone in p0's hand with mana, set the library, cast it."""
    cap = ImprovisationCapstone(owner=None)
    set_board_state(
        game, 0, hand=[cap], mana={ManaType.RED: 2, ManaType.COLORLESS: 5}
    )
    _set_library(game, game.players[0], library)
    for ans in answers:
        game.players[0]._script.append(ans)
    cast_spell(game, 0, "Improvisation Capstone")
    return cap


def _exile(game, player):
    return player.zones[Zone.EXILE].get_all()


def _library(game, player):
    return player.zones[Zone.LIBRARY].get_all()


class TestProperties:
    def test_is_sorcery(self):
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)

    def test_name(self):
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self):
        assert (
            ImprovisationCapstone(owner=None).mana_cost
            == ManaCost.parse("{5}{R}{R}")
        )

    def test_lesson_subtype(self):
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes


class TestExileUntilMV4:
    def test_exiles_until_total_mv_four(self):
        game = create_game()
        p0 = game.players[0]
        bear = _spell("MV2", "{1}{R}")   # MV 2
        bolt = _spell("MV1", "{R}")      # MV 1
        big = _spell("MV3", "{2}{R}")    # MV 3
        extra = _spell("MV9", "{8}{R}")  # MV 9, should stay
        _cast_capstone(game, [bear, bolt, big, extra], [False, False, False])
        ex = _exile(game, p0)
        assert bear in ex and bolt in ex and big in ex
        assert extra not in ex
        assert extra in _library(game, p0)

    def test_single_high_mv_card_stops(self):
        game = create_game()
        p0 = game.players[0]
        big = _spell("Big", "{8}{R}")    # MV 9 alone exceeds 4
        rest = _spell("Rest", "{R}")
        _cast_capstone(game, [big, rest], [False])
        assert big in _exile(game, p0)
        assert rest in _library(game, p0)

    def test_lands_dont_count_toward_total(self):
        game = create_game()
        p0 = game.players[0]
        l1, l2 = _land("L1"), _land("L2")
        bolt = _spell("Bolt", "{R}")     # MV 1
        bear = _spell("Bear", "{1}{R}")  # MV 2
        big = _spell("Big", "{2}{R}")    # MV 3 -> total 6
        _cast_capstone(game, [l1, l2, bolt, bear, big], [False, False, False])
        ex = _exile(game, p0)
        for c in (l1, l2, bolt, bear, big):
            assert c in ex

    def test_stops_when_library_empty(self):
        game = create_game()
        p0 = game.players[0]
        only = _spell("Only", "{1}{R}")  # MV 2 < 4, library then empty
        _cast_capstone(game, [only], [False])
        assert only in _exile(game, p0)
        assert _library(game, p0) == []


class TestFreeCast:
    def test_accept_casts_and_resolves(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, life=20)
        spell = _spell("Recollect", "{4}{R}")  # MV 5, alone stops the loop
        _cast_capstone(game, [spell], [True])  # accept the free cast
        assert spell in p0.zones[Zone.GRAVEYARD].get_all()
        assert p0.life == 23

    def test_decline_keeps_in_exile(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, life=20)
        spell = _spell("Recollect", "{4}{R}")
        _cast_capstone(game, [spell], [False])
        assert spell in _exile(game, p0)
        assert p0.life == 20

    def test_land_never_castable(self):
        game = create_game()
        p0 = game.players[0]
        land = _land("Island")
        big = _spell("Big", "{4}{R}")  # MV 5 stops the loop
        # Only one yes/no prompt (for big); land is never offered.
        _cast_capstone(game, [land, big], [False])
        assert land in _exile(game, p0)


class TestParadigm:
    def test_spell_exiled_not_graveyard(self):
        game = create_game()
        p0 = game.players[0]
        decline = _spell("Decline", "{4}{R}")
        cap = _cast_capstone(game, [decline], [False])
        assert cap in _exile(game, p0)
        assert cap not in p0.zones[Zone.GRAVEYARD].get_all()

    def test_recast_at_first_main_phase(self):
        game = create_game()
        p0 = game.players[0]
        decline = _spell("Decline", "{4}{R}")
        cap = _cast_capstone(game, [decline], [False])
        # Refill the library for the recast copy to dig into.
        spell2 = _spell("Spell2", "{4}{R}")
        _set_library(game, p0, [spell2])
        p0._script.append(True)   # Paradigm — yes, cast a copy
        p0._script.append(False)  # copy declines its own free cast
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p0, is_precombat=True)
        )
        from test_utils import _resolve_top_of_stack

        _resolve_top_of_stack(game)
        assert spell2 in _exile(game, p0)
        assert cap in _exile(game, p0)  # original copy stays in exile

    def test_no_recast_on_opponent_main(self):
        game = create_game()
        p0, p1 = game.players
        decline = _spell("Decline", "{4}{R}")
        _cast_capstone(game, [decline], [False])
        spell2 = _spell("Spell2", "{4}{R}")
        _set_library(game, p0, [spell2])
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True)
        )
        from test_utils import _resolve_top_of_stack

        _resolve_top_of_stack(game)
        assert spell2 in _library(game, p0)

    def test_no_recast_postcombat(self):
        game = create_game()
        p0 = game.players[0]
        decline = _spell("Decline", "{4}{R}")
        _cast_capstone(game, [decline], [False])
        spell2 = _spell("Spell2", "{4}{R}")
        _set_library(game, p0, [spell2])
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p0, is_precombat=False)
        )
        from test_utils import _resolve_top_of_stack

        _resolve_top_of_stack(game)
        assert spell2 in _library(game, p0)
