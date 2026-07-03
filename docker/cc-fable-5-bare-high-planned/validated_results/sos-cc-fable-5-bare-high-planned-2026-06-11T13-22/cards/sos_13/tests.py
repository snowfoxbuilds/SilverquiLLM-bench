"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import Keyword, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _ability_instance(card, player):
    ab = card.get_activated_abilities()[0]
    return ActivatedAbilityInstance(
        source=card, controller=player, cost=ab.cost, effect=ab.effect,
    )


class TestEmeritusETB:
    def test_bare_construction_uses_full_dfc_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_etb_target_player_creates_inkling_no_prepare_when_even(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        # ETB trigger consumes the scripted player choice.
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p2])

        inklings = [c for c in p2.zones[Zone.BATTLEFIELD].get_all()
                    if c.name == "Inkling"]
        assert len(inklings) == 1
        assert Keyword.FLYING in inklings[0].keywords
        assert inklings[0].is_token
        # 1 creature each — opponent does NOT control more — not prepared.
        assert emeritus.prepared is False

    def test_etb_becomes_prepared_when_opponent_has_more(self):
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        bears = [Creature(name=f"B{i}", base_power=2, base_toughness=2)
                 for i in range(2)]
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        set_board_state(game, 1, battlefield=bears)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p2])
        # Opponent: 2 bears + Inkling = 3 vs our 1 — prepared.
        assert emeritus.prepared is True


class TestPreparedCast:
    def _prepared_game(self):
        game = create_game(scripts=([], ["pass"] * 8))
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[bear])
        emeritus.prepared = True
        return game, p1, p2, emeritus, bear

    def test_cast_copy_exiles_creature_and_unprepares(self):
        game, p1, p2, emeritus, bear = self._prepared_game()
        activate_ability(game, p1, _ability_instance(emeritus, p1))
        assert p1.mana_pool.total() == 0  # {W} paid
        # pass, pass -> ability resolves (choose_target: bear); then drain.
        p1._script.extend(["pass", bear] + ["pass"] * 6)
        priority_loop(game)

        assert p2.zones[Zone.EXILE].contains(bear)
        assert p2.life == 22                # gained life equal to its power
        assert emeritus.prepared is False

    def test_not_prepared_cannot_activate(self):
        game, p1, p2, emeritus, bear = self._prepared_game()
        emeritus.prepared = False
        with pytest.raises(AbilityError):
            activate_ability(game, p1, _ability_instance(emeritus, p1))
        assert p1.mana_pool.total() == 1   # nothing paid

    def test_no_legal_target_stays_prepared(self):
        game = create_game(scripts=([], ["pass"] * 8))
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        emeritus.prepared = True
        activate_ability(game, p1, _ability_instance(emeritus, p1))
        # Emeritus itself is a creature, so Swords CAN target it — script
        # declining is not possible; instead verify with an empty board:
        # remove Emeritus from the battlefield before resolution.
        p1.zones[Zone.BATTLEFIELD].remove(emeritus)
        p1._script.extend(["pass"] * 6)
        priority_loop(game)

        assert emeritus.prepared is True   # cast failed, still prepared
        assert len(p1.zones[Zone.EXILE]) == 0
