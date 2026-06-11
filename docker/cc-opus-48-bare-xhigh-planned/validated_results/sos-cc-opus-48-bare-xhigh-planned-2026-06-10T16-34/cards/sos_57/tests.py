"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state, advance_to_phase


class BigZap(Instant):
    """Target spell: deal 5 damage to the opponent on resolve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Big Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        opp = [p for p in game.players if p is not self.controller][0]
        from engine.game import deal_damage

        deal_damage(game, self, opp, 5)


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _put_target_on_stack(game, caster, target_card, mana):
    target_card.owner = caster
    target_card.controller = caster
    game.get_hand(caster).add(target_card)
    for mt, amt in mana.items():
        caster.mana_pool.add(mt, amt)
    engine_cast_spell(game, caster, target_card)
    return game.stack.peek()


class TestProperties:
    def test_static(self):
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert isinstance(card, Instant)


class TestCanCast:
    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        card = ManaSculpt(owner=game.players[0], controller=game.players[0])
        assert card.can_cast(game) is False

    def test_can_cast_with_spell_on_stack(self):
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)
        _put_target_on_stack(game, p2, BigZap(owner=None), {ManaType.COLORLESS: 2})
        assert sculpt.can_cast(game) is True


class TestCounter:
    def test_counters_target_spell(self):
        game = create_game()
        p1, p2 = game.players
        target_so = _put_target_on_stack(game, p2, BigZap(owner=None), {ManaType.COLORLESS: 2})
        assert getattr(target_so.source, "mana_spent", None) == 2

        sculpt = ManaSculpt(owner=p1, controller=p1)
        game.get_hand(p1).add(sculpt)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1.mana_pool.add(ManaType.BLUE, 2)
        p1._script.append(target_so)  # target choice
        engine_cast_spell(game, p1, sculpt)
        _resolve_all(game)
        # Big Zap was countered → it's in p2's graveyard and never dealt damage.
        assert game.get_graveyard(p2).contains(target_so.source)
        assert p1.life == 20  # the 5-damage spell did not resolve


class TestDelayedMana:
    def _counter_and_advance(self, with_wizard, target_card, target_mana):
        game = create_game()
        p1, p2 = game.players
        bf = []
        if with_wizard:
            bf.append(Creature(name="Wiz", base_power=1, base_toughness=1, subtypes={"Wizard"}))
        set_board_state(game, 0, battlefield=bf)
        # p2 casts a spell; p1 counters with Mana Sculpt on turn 1.
        target_so = _put_target_on_stack(game, p2, target_card, target_mana)
        sculpt = ManaSculpt(owner=p1, controller=p1)
        game.get_hand(p1).add(sculpt)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1.mana_pool.add(ManaType.BLUE, 2)
        p1._script.append(target_so)
        engine_cast_spell(game, p1, sculpt)
        _resolve_all(game)
        # Simulate reaching p1's next precombat main (a later turn).
        game.active_player_index = 0
        game.turn_number = 3
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_all(game)
        return game, p1

    def test_wizard_grants_mana_equal_to_spent(self):
        game, p1 = self._counter_and_advance(
            with_wizard=True, target_card=BigZap(owner=None),
            target_mana={ManaType.COLORLESS: 2})
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self):
        game, p1 = self._counter_and_advance(
            with_wizard=False, target_card=BigZap(owner=None),
            target_mana={ManaType.COLORLESS: 2})
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_amount_reflects_a_four_mana_spell(self):
        big = BigZap(owner=None)
        big.mana_cost = ManaCost.parse("{4}")
        game, p1 = self._counter_and_advance(
            with_wizard=True, target_card=big, target_mana={ManaType.COLORLESS: 4})
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_delayed_mana_is_one_shot(self):
        game, p1 = self._counter_and_advance(
            with_wizard=True, target_card=BigZap(owner=None),
            target_mana={ManaType.COLORLESS: 2})
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        # Advance to a later main phase — no more mana should appear.
        game.turn_number = 5
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        p1.mana_pool.empty()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_all(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
