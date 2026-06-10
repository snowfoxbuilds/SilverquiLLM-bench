"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast
from engine.state_based_actions import resolve_state_based_actions
from engine.types import (
    ManaCost,
    ManaType,
    Phase,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class _Zap3(Instant):
    """{3} instant: deal 2 damage to target player (mana_spent = 3)."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Zap3")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        players = set(game.players)
        return [
            TargetRequirement(
                filter_fn=lambda o: o in players,
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game):
        from engine.game import deal_damage

        t = (getattr(self, "chosen_targets", []) or [None])[0]
        if t is not None:
            deal_damage(game, self, t, 2)


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _advance_to_active0_precombat(game):
    """Advance phases until player 0's next precombat main (a later turn)."""
    for _ in range(60):
        game.advance_phase()
        if game.phase == Phase.PRECOMBAT_MAIN and game.active_player_index == 0:
            return
    raise AssertionError("did not reach player 0's precombat main")


def _setup_counter(p0_wizard: bool):
    """p1 casts Zap3; p0 counters it with Mana Sculpt. Returns game/players."""
    game = create_game()
    p0, p1 = game.players
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    # p1 casts Zap3 at p0 (stays on the stack).
    zap = _Zap3(owner=p1, controller=p1)
    set_board_state(game, 1, hand=[zap], mana={ManaType.COLORLESS: 3})
    p1._script.appendleft(p0)
    engine_cast(game, p1, zap)
    zap_so = game.stack.peek()
    # p0 casts Mana Sculpt targeting Zap3.
    bf = [Creature(name="Wiz", subtypes={"Wizard"}, base_power=1,
                   base_toughness=1)] if p0_wizard else []
    set_board_state(game, 0, hand=[ManaSculpt(owner=None)], battlefield=bf,
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    p0._script.appendleft(zap_so)
    ms = next(c for c in game.get_hand(p0).get_all() if c.name == "Mana Sculpt")
    engine_cast(game, p0, ms)
    _resolve_all(game)
    return game, p0, p1, zap


class TestProperties:
    def test_static(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert isinstance(card, Instant)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_empty_stack(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=None).can_cast(game) is False


class TestCounter:
    def test_counters_target_spell(self) -> None:
        game, p0, p1, zap = _setup_counter(p0_wizard=True)
        # Zap3 countered → in p1's graveyard, never dealt damage.
        assert game.get_graveyard(p1).contains(zap)
        assert p0.life == 20

    def test_wizard_adds_colorless_next_main(self) -> None:
        game, p0, p1, zap = _setup_counter(p0_wizard=True)
        _advance_to_active0_precombat(game)
        _resolve_all(game)  # resolve the delayed-mana trigger
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3  # = mana spent on Zap3

    def test_no_wizard_no_mana(self) -> None:
        game, p0, p1, zap = _setup_counter(p0_wizard=False)
        _advance_to_active0_precombat(game)
        _resolve_all(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
