"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares, SwordsToPlowshares
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import _resolve_top_of_stack


def _sorcery_speed(game, idx=0):
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = idx


class TestEmeritusOfTruce:
    def test_name_is_full_double_faced(self):
        """Card name includes both faces."""
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_etb_creates_inkling_token(self):
        """ETB trigger creates a 1/1 Inkling with flying for target player."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.controller = p1
        emeritus.register_triggers(game)

        # Manually fire ETB (set_board_state doesn't call move_to_zone)
        # Script: choose p2 as target player
        p1._script.appendleft(p2)

        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1)
        )
        _resolve_top_of_stack(game)

        # p2 should have an Inkling token on their battlefield
        p2_bf = game.get_battlefield(p2).get_all()
        inkling = next((c for c in p2_bf if "Inkling" in getattr(c, "subtypes", set())), None)
        assert inkling is not None
        assert Keyword.FLYING in inkling.keywords
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1

    def test_prepared_when_opponent_has_more_creatures(self):
        """Becomes prepared if opponent controls more creatures."""
        game = create_game()
        p1, p2 = game.players

        # p2 has 3 creatures, p1 will have emeritus + 1 inkling (token for p1) = 2 total
        bear1 = Creature(name="Bear1", base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear2", base_power=2, base_toughness=2)
        bear3 = Creature(name="Bear3", base_power=2, base_toughness=2)
        emeritus = EmeritusOfTruceSwordsToPlowshares()

        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[bear1, bear2, bear3])
        emeritus.controller = p1
        emeritus.register_triggers(game)

        # Script: choose p1 as target player for Inkling (p1 gets 1 inkling → 2 creatures total)
        # p2 still has 3, so p2 > p1 → prepared
        p1._script.appendleft(p1)

        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1)
        )
        _resolve_top_of_stack(game)

        assert emeritus._prepared is True

    def test_not_prepared_when_equal_creatures(self):
        """Does not become prepared if no opponent controls more creatures."""
        game = create_game()
        p1, p2 = game.players

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        emeritus = EmeritusOfTruceSwordsToPlowshares()

        # p1 has emeritus + bear = 2 creatures, p2 has 1 bear
        set_board_state(game, 0, battlefield=[emeritus, bear])
        set_board_state(game, 1, battlefield=[Creature(name="OppBear", base_power=2, base_toughness=2)])
        emeritus.controller = p1
        emeritus.register_triggers(game)

        p1._script.appendleft(p1)

        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game, EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1)
        )
        _resolve_top_of_stack(game)

        assert emeritus._prepared is False

    def test_swords_exiles_creature_and_gains_life(self):
        """Swords to Plowshares: exile creature, controller gains power in life."""
        game = create_game()
        p1, p2 = game.players

        target = Creature(name="BigBear", base_power=5, base_toughness=5)
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target], life=20)

        swords = SwordsToPlowshares()
        swords.owner = p1
        swords.controller = p1
        swords.chosen_targets = [target]
        swords.on_resolve(game)

        # Target should be in exile
        assert target in p2.zones[Zone.EXILE].get_all()
        # p2 gained 5 life (power=5)
        assert p2.life == 25

    def test_cast_prepared_swords_via_activated_ability(self):
        """While prepared, activated ability lets you cast Swords copy."""
        game = create_game()
        p1, p2 = game.players

        target = Creature(name="Target", base_power=3, base_toughness=3)
        target.owner = p2
        target.controller = p2
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[target], life=20)
        emeritus.controller = p1
        emeritus._prepared = True
        _sorcery_speed(game)

        # Activate the prepared ability (cast swords copy)
        abilities = emeritus.get_activated_abilities()
        assert len(abilities) == 1
        instance = ActivatedAbilityInstance(
            source=emeritus,
            controller=p1,
            cost=abilities[0].cost,
            effect=abilities[0].effect,
            is_mana_ability=False,
        )

        # Script target for Swords
        p1._script.appendleft(target)
        activate_ability(game, p1, instance)
        _resolve_top_of_stack(game)

        # Target should be in exile; emeritus should be unprepared
        assert target in p2.zones[Zone.EXILE].get_all()
        assert emeritus._prepared is False
        # p2 gains 3 life (power=3)
        assert p2.life == 23
