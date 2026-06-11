"""Tests for sos_13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest
from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, _resolve_top_of_stack


class TestEmeritusProperties:
    def test_name(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares().name == "Emeritus of Truce // Swords to Plowshares"

    def test_stats(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares()
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_is_creature(self) -> None:
        assert CardType.CREATURE in EmeritusOfTruceSwordsToPlowshares().card_types

    def test_cat_cleric_subtype(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares()
        assert "Cat" in c.subtypes
        assert "Cleric" in c.subtypes


class TestSwordsToPlowshares:
    def test_name(self) -> None:
        assert SwordsToPlowshares().name == "Swords to Plowshares"

    def test_exiles_creature_and_grants_life(self) -> None:
        """Exile target creature; its controller gains life equal to its power."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]

        target = Creature(name="Bear", base_power=2, base_toughness=2)
        target.modified_power = 2
        set_board_state(game, 1, battlefield=[target])

        swords = SwordsToPlowshares()
        swords.controller = p0
        swords.owner = p0
        swords.chosen_targets = [target]

        p1_life_before = p1.life
        swords.on_resolve(game)

        assert p1.zones[Zone.EXILE].contains(target)
        assert not game.get_battlefield(p1).contains(target)
        assert p1.life == p1_life_before + 2


class TestETBTokenCreation:
    def test_etb_creates_inkling_token(self) -> None:
        """ETB trigger creates a 1/1 flying Inkling for the targeted player."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.register_triggers(game)

        # No opponent creatures, no creatures for us either → not prepared
        # Script: p0 chooses p1 as the target player
        p0._script.append(p1)

        # Fire ETB event
        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p0)
        )
        _resolve_top_of_stack(game)

        # P1 should have an Inkling token
        bf_p1 = game.get_battlefield(p1)
        inklings = [c for c in bf_p1.get_all() if getattr(c, "name", None) == "Inkling"]
        assert len(inklings) == 1
        assert Keyword.FLYING in inklings[0].keywords

    def test_etb_not_prepared_when_equal_creatures(self) -> None:
        """Emeritus is NOT prepared when opponent doesn't control MORE creatures."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        # Equal creatures: emeritus on p0's side, one on p1's side
        opp_creature = Creature(name="Opp", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[opp_creature])
        emeritus.register_triggers(game)

        # Script: choose self as target player
        p0._script.append(p0)

        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p0)
        )
        _resolve_top_of_stack(game)

        # 1 creature each — not prepared
        assert emeritus._prepared is False

    def test_etb_prepared_when_opponent_has_more(self) -> None:
        """Emeritus becomes prepared when opponent controls more creatures after token."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        # Opponent has 3 creatures; we have 1 (emeritus)
        # Token goes to p0 → p0 has 2, p1 has 3 → p1 > p0 → prepared
        opp1 = Creature(name="Opp1", base_power=1, base_toughness=1)
        opp2 = Creature(name="Opp2", base_power=1, base_toughness=1)
        opp3 = Creature(name="Opp3", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[opp1, opp2, opp3])
        emeritus.register_triggers(game)

        # Script: choose self as target player (token goes to p0)
        p0._script.append(p0)

        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p0)
        )
        _resolve_top_of_stack(game)

        # After token: p0 has 2 (emeritus + inkling), p1 has 3 → prepared
        assert emeritus._prepared is True


class TestPreparedAbility:
    def test_prepared_ability_casts_swords_copy(self) -> None:
        """When prepared, the activated ability casts a Swords copy."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        emeritus._prepared = True
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        target.modified_power = 2
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[target])

        from engine.game_state import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ability = emeritus.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=emeritus,
            controller=p0,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        )
        activate_ability(game, p0, instance)

        # Stack has the prepared ability (non-mana)
        assert not game.stack.is_empty()

        # Script target for Swords: target creature
        p0._script.append(target)
        _resolve_top_of_stack(game)

        # Swords resolved: target exiled, p1 gained 2 life, emeritus unprepared
        assert p1.zones[Zone.EXILE].contains(target)
        assert p1.life == 22  # 20 + 2
        assert emeritus._prepared is False

    def test_prepared_cost_fails_when_not_prepared(self) -> None:
        """Cannot activate the prepared ability when not prepared."""
        from engine.abilities import AbilityError

        game = create_game()
        p0 = game.players[0]
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        emeritus._prepared = False
        set_board_state(game, 0, battlefield=[emeritus])

        from engine.game_state import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ability = emeritus.get_activated_abilities()[0]
        instance = ActivatedAbilityInstance(
            source=emeritus,
            controller=p0,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
        )
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, p0, instance)
