"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


class LifeSip(Instant):
    """Test instant with an observable, untargeted effect: gain 1 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Sip")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 1


def _setup(extra_battlefield=None):
    game = create_game()
    p1 = game.players[0]
    sq = SilverquillTheDisputant(owner=p1)
    battlefield = [sq] + (extra_battlefield or [])
    set_board_state(game, 0, battlefield=battlefield,
                    mana={ManaType.COLORLESS: 1})
    sq.register_triggers(game)
    return game, p1, sq


class TestSilverquillCasualty:
    def test_sacrifice_copies_the_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, _ = _setup([bear])
        spell = LifeSip(owner=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        p1._script.append(bear)  # casualty: sacrifice the bear
        cast_spell(game, 0, "Life Sip")
        assert p1.life == 22  # original + copy
        assert game.get_graveyard(p1).contains(bear)

    def test_decline_no_copy(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, _ = _setup([bear])
        spell = LifeSip(owner=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        p1._script.append(None)  # decline casualty
        cast_spell(game, 0, "Life Sip")
        assert p1.life == 21
        assert game.get_battlefield(p1).contains(bear)

    def test_zero_power_creature_not_eligible(self):
        wall = Creature(name="Wall", base_power=0, base_toughness=4)
        game, p1, sq = _setup([wall])
        spell = LifeSip(owner=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 1})
        # Only Silverquill (power 4) is eligible; sacrifice it.
        p1._script.append(sq)
        cast_spell(game, 0, "Life Sip")
        assert p1.life == 22
        assert game.get_graveyard(p1).contains(sq)
        assert game.get_battlefield(p1).contains(wall)

    def test_opponents_spells_not_granted_casualty(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, _ = _setup([bear])
        p2 = game.players[1]
        spell = LifeSip(owner=p2)
        set_board_state(game, 1, hand=[spell], mana={ManaType.COLORLESS: 1})
        game.active_player_index = 1
        game.priority_player_index = 1
        # No casualty prompt should occur — an exhausted script would raise.
        cast_spell(game, 1, "Life Sip")
        assert p2.life == 21
        assert game.get_battlefield(p1).contains(bear)

    def test_copy_keeps_targets_when_declined(self):
        from cards.fdn.fdn_192.card_impl import BurstLightning

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, _ = _setup([bear])
        p2 = game.players[1]
        bolt = BurstLightning(owner=p1)
        set_board_state(game, 0, hand=[bolt], mana={ManaType.RED: 1})
        p1._script.append(bear)   # casualty sacrifice
        p1._script.append(False)  # keep the same targets for the copy
        cast_spell(game, 0, "Burst Lightning", targets=[p2])
        assert p2.life == 16  # 2 (copy) + 2 (original)
