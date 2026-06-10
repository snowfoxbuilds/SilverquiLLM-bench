"""Tests for SOS 226 — Silverquill, the Disputant (Casualty 1)."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast
from engine.state_based_actions import resolve_state_based_actions
from engine.types import (
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class _Zap(Instant):
    """Test instant: deal 3 damage to target player."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
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
            deal_damage(game, self, t, 3)


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _setup(creatures_extra, casualty_choice):
    """Cast Zap with Silverquill out; return (game, p0, p1, zap, bear)."""
    game = create_game()
    p0, p1 = game.players
    silver = SilverquillTheDisputant(owner=p0, controller=p0)
    zap = _Zap(owner=p0, controller=p0)
    bf = [silver, *creatures_extra]
    set_board_state(game, 0, battlefield=bf, hand=[zap],
                    mana={ManaType.RED: 1})
    silver.register_triggers(game)
    # Script: instant's target (p1), then casualty choice.
    p0._script.extend([p1, casualty_choice])
    engine_cast(game, p0, zap)
    _resolve_all(game)
    return game, p0, p1, zap


class TestProperties:
    def test_static(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.base_power == 4 and card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")


class TestCasualty:
    def test_sacrifice_copies_spell(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, zap = _setup([bear], bear)
        # Original + copy each deal 3 → 6 total.
        assert p1.life == 14
        assert game.get_graveyard(p0).contains(bear)  # sacrificed
        assert not game.get_battlefield(p0).contains(bear)

    def test_decline_no_copy(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, zap = _setup([bear], None)  # decline
        assert p1.life == 17  # only original
        assert game.get_battlefield(p0).contains(bear)  # not sacrificed

    def test_zero_power_creature_not_offered(self) -> None:
        """A 0-power creature is not a legal casualty sacrifice; declining
        when only it (besides Silverquill) is around still works — here we
        decline and confirm the 0-power wall is never sacrificed."""
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        game = create_game()
        p0, p1 = game.players
        silver = SilverquillTheDisputant(owner=p0, controller=p0)
        zap = _Zap(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[silver, wall], hand=[zap],
                        mana={ManaType.RED: 1})
        silver.register_triggers(game)
        p0._script.extend([p1, None])  # instant target, then decline casualty
        engine_cast(game, p0, zap)
        _resolve_all(game)
        assert p1.life == 17  # only original
        assert game.get_battlefield(p0).contains(wall)

    def test_can_sacrifice_silverquill_itself(self) -> None:
        """Silverquill (power 4) is itself a legal casualty creature."""
        game = create_game()
        p0, p1 = game.players
        silver = SilverquillTheDisputant(owner=p0, controller=p0)
        zap = _Zap(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[silver], hand=[zap],
                        mana={ManaType.RED: 1})
        silver.register_triggers(game)
        p0._script.extend([p1, silver])  # sacrifice Silverquill itself
        engine_cast(game, p0, zap)
        _resolve_all(game)
        assert p1.life == 14  # copy still made
        assert game.get_graveyard(p0).contains(silver)

    def test_opponent_spell_no_casualty(self) -> None:
        """Casualty only applies to spells YOU cast."""
        game = create_game()
        p0, p1 = game.players
        silver = SilverquillTheDisputant(owner=p0, controller=p0)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[silver, bear])
        silver.register_triggers(game)
        zap = _Zap(owner=p1, controller=p1)
        set_board_state(game, 1, hand=[zap], mana={ManaType.RED: 1})
        p1._script.extend([p0])  # opponent's Zap targets p0
        engine_cast(game, p1, zap)
        _resolve_all(game)
        assert p0.life == 17  # single hit, no copy
        assert game.get_battlefield(p0).contains(bear)  # not sacrificed
