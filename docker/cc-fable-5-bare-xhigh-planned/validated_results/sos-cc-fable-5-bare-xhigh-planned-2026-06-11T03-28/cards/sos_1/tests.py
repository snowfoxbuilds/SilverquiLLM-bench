"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, declare_attackers, set_board_state, cast_spell


class _Zap(Instant):
    """Helper instant: controller gains 1 life on resolution."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


class TestDawningArchaicProperties:
    def test_static_data(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert Keyword.REACH in card.keywords
        assert card.base_power == 7
        assert card.base_toughness == 7
        assert Supertype.LEGENDARY in card.supertypes


class TestDawningArchaicCostReduction:
    def test_costs_one_less_per_instant_sorcery_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1)
        graveyard = [_Zap() for _ in range(4)] + [
            Creature(name="Dead Bear", base_power=2, base_toughness=2)
        ]
        set_board_state(game, 0, hand=[archaic], graveyard=graveyard,
                        mana={ManaType.COLORLESS: 6})
        # {10} − 4 = {6}; the creature card in the graveyard does not count.
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p1).contains(archaic)

    def test_reduction_clamps_at_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1)
        set_board_state(game, 0, hand=[archaic],
                        graveyard=[_Zap() for _ in range(15)], mana={})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p1).contains(archaic)

    def test_no_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1)
        set_board_state(game, 0, hand=[archaic], graveyard=[],
                        mana={ManaType.COLORLESS: 9})
        try:
            cast_spell(game, 0, "The Dawning Archaic")
            cast_ok = True
        except Exception:
            cast_ok = False
        assert not cast_ok
        assert game.get_hand(p1).contains(archaic)


class TestDawningArchaicAttackTrigger:
    def _setup_attacking_game(self, graveyard: list[Any]):
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard)
        # set_board_state bypasses move_to_zone, so mirror its trigger
        # registration step explicitly.
        archaic.register_triggers(game)
        archaic.summoning_sick = False
        return game, p1, archaic

    def test_attack_casts_sole_candidate_and_exiles_it(self) -> None:
        zap = _Zap()
        game, p1, archaic = self._setup_attacking_game([zap])
        p2 = game.players[1]
        declare_attackers(game, ["The Dawning Archaic"])
        # Trigger is on the stack: pass priorities, accept the "may",
        # then pass priorities for the free-cast Zap.
        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        # Zap resolved (life gain) and was exiled instead of going back
        # to the graveyard.
        assert p1.life == 21
        assert game.get_exile(p1).contains(zap)
        assert not game.get_graveyard(p1).contains(zap)

    def test_attack_may_decline(self) -> None:
        zap = _Zap()
        game, p1, archaic = self._setup_attacking_game([zap])
        p2 = game.players[1]
        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.life == 20
        assert game.get_graveyard(p1).contains(zap)

    def test_attack_with_no_legal_candidate_does_nothing(self) -> None:
        bear = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        game, p1, archaic = self._setup_attacking_game([bear])
        p2 = game.players[1]
        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.get_graveyard(p1).contains(bear)
        assert p1.remaining_choices == 0

    def test_attack_with_multiple_candidates_prompts_choice(self) -> None:
        zap1, zap2 = _Zap(), _Zap()
        game, p1, archaic = self._setup_attacking_game([zap1, zap2])
        p2 = game.players[1]
        declare_attackers(game, ["The Dawning Archaic"])
        # choose_card answer: zap2
        p1._script.extend(["pass", zap2, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert game.get_exile(p1).contains(zap2)
        assert game.get_graveyard(p1).contains(zap1)
        assert p1.life == 21
