"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Color, Keyword, ManaCost, ManaType, Phase, Step, Supertype
from test_utils import create_game, set_board_state


def _put_on_top_of_library(game, player, *cards) -> None:
    """Put *cards* onto *player*'s library in bottom-to-top order."""
    library = game.get_library(player)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _register_lorehold(game, lorehold: LoreholdTheHistorian) -> None:
    """Register Lorehold's battlefield abilities and apply static effects."""
    lorehold.register_triggers(game)
    game.effect_manager.apply_all(game)


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_legendary_elder_dragon_with_flying_and_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_has_expected_mana_cost_colors_and_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.colors == {Color.RED, Color.WHITE}
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestLoreholdTheHistorianMiracleGrant:
    """Lorehold should grant miracle to your instants and sorceries in hand."""

    def test_your_instants_and_sorceries_in_hand_gain_miracle_with_cost_two(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        your_instant = Instant(name="Lightning Notes", owner=player, controller=player)
        your_sorcery = Sorcery(name="Lecture Finale", owner=player, controller=player)

        set_board_state(game, 0, battlefield=[lorehold], hand=[your_instant, your_sorcery])

        _register_lorehold(game, lorehold)

        assert "Miracle" in your_instant.non_evergreen_keywords
        assert "Miracle" in your_sorcery.non_evergreen_keywords
        assert getattr(your_instant, "miracle_cost", None) == ManaCost.parse("{2}")
        assert getattr(your_sorcery, "miracle_cost", None) == ManaCost.parse("{2}")

    def test_creatures_and_opponents_hand_cards_do_not_gain_miracle(self) -> None:
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        your_creature = Creature(
            name="Campus Bear",
            owner=player,
            controller=player,
            base_power=2,
            base_toughness=2,
        )
        opponent_instant = Instant(name="Enemy Notes", owner=opponent, controller=opponent)

        set_board_state(game, 0, battlefield=[lorehold], hand=[your_creature])
        set_board_state(game, 1, hand=[opponent_instant])

        _register_lorehold(game, lorehold)

        assert "Miracle" not in your_creature.non_evergreen_keywords
        assert "Miracle" not in opponent_instant.non_evergreen_keywords


class TestLoreholdTheHistorianMiracleCasting:
    """Lorehold should enable first-draw miracle casting through the public API."""

    def test_first_drawn_spell_can_be_cast_for_miracle_cost_from_draw_step(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        drawn_spell = Sorcery(
            name="Lecture Rewrite",
            owner=player,
            controller=player,
            mana_cost=ManaCost.parse("{5}{R}"),
        )

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_on_top_of_library(game, player, drawn_spell)
        _register_lorehold(game, lorehold)
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW

        drawn = draw_card(game, player)

        assert drawn is drawn_spell
        assert player.cards_drawn_this_turn == 1
        assert drawn_spell.has_miracle is True
        assert drawn_spell.miracle_eligible is True
        assert drawn_spell.can_cast_for_miracle(game) is True

        drawn_spell.cast_for_miracle(game)
        stack_obj = game.stack.peek()

        assert stack_obj is not None
        assert stack_obj.source is drawn_spell
        assert not game.get_hand(player).contains(drawn_spell)
        assert drawn_spell.cast_via_miracle is True
        assert drawn_spell.total_mana_spent_to_cast == 2
        assert player.mana_pool.total() == 0

        resolved = game.stack.pop()
        resolved.on_resolve(game)

        assert game.get_graveyard(player).contains(drawn_spell)

    def test_second_card_drawn_this_turn_is_not_miracle_eligible(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        first_draw = Creature(
            name="Campus Archivist",
            owner=player,
            controller=player,
            base_power=1,
            base_toughness=3,
        )
        second_draw = Instant(
            name="Late Revelation",
            owner=player,
            controller=player,
            mana_cost=ManaCost.parse("{4}{U}"),
        )

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        _put_on_top_of_library(game, player, second_draw, first_draw)
        _register_lorehold(game, lorehold)

        assert draw_card(game, player) is first_draw
        assert draw_card(game, player) is second_draw
        assert player.cards_drawn_this_turn == 2
        assert second_draw.has_miracle is True
        assert second_draw.miracle_eligible is False
        assert second_draw.can_cast_for_miracle(game) is False

    def test_turn_rollover_resets_draw_count_and_miracle_eligibility(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        first_turn_draw = Instant(
            name="Opening Argument",
            owner=player,
            controller=player,
            mana_cost=ManaCost.parse("{3}{U}"),
        )
        next_turn_draw = Sorcery(
            name="Fresh Lesson Plan",
            owner=player,
            controller=player,
            mana_cost=ManaCost.parse("{4}{R}"),
        )

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        _put_on_top_of_library(game, player, first_turn_draw)
        _register_lorehold(game, lorehold)

        assert draw_card(game, player) is first_turn_draw
        assert player.cards_drawn_this_turn == 1
        assert first_turn_draw.miracle_eligible is True

        while game.turn_number == 1:
            game.advance_phase()

        assert player.cards_drawn_this_turn == 0
        assert first_turn_draw.miracle_eligible is False

        _put_on_top_of_library(game, player, next_turn_draw)

        assert draw_card(game, player) is next_turn_draw
        assert player.cards_drawn_this_turn == 1
        assert next_turn_draw.miracle_eligible is True
        assert next_turn_draw.can_cast_for_miracle(game) is True


class TestLoreholdTheHistorianUpkeepTrigger:
    """Lorehold should loot during each opponent's upkeep only."""

    def test_triggers_on_each_opponents_upkeep_only(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)

        set_board_state(game, 0, battlefield=[lorehold])
        _register_lorehold(game, lorehold)

        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert len(game.stack) == 1

    def test_may_discard_a_card_to_draw_a_card(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        discard_me = Instant(name="Spent Notes", owner=player, controller=player)
        keep_me = Sorcery(name="Held Thesis", owner=player, controller=player)
        drawn_card = Creature(
            name="Fresh Research",
            owner=player,
            controller=player,
            base_power=1,
            base_toughness=1,
        )

        player.choose_yes_no = lambda prompt: True
        player.choose_card = lambda cards, description: discard_me

        set_board_state(game, 0, battlefield=[lorehold], hand=[discard_me, keep_me])
        _put_on_top_of_library(game, player, drawn_card)
        _register_lorehold(game, lorehold)

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(player).contains(discard_me)
        assert game.get_hand(player).contains(keep_me)
        assert game.get_hand(player).contains(drawn_card)
        assert not game.get_library(player).contains(drawn_card)

    def test_may_decline_to_discard_and_not_draw(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        kept_card = Instant(name="Filed Away", owner=player, controller=player)
        drawn_card = Sorcery(name="Unread Chapter", owner=player, controller=player)

        player.choose_yes_no = lambda prompt: False

        set_board_state(game, 0, battlefield=[lorehold], hand=[kept_card])
        _put_on_top_of_library(game, player, drawn_card)
        _register_lorehold(game, lorehold)

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_hand(player).contains(kept_card)
        assert not game.get_hand(player).contains(drawn_card)
        assert game.get_library(player).contains(drawn_card)
        assert not game.get_graveyard(player).contains(kept_card)

    def test_trigger_noops_when_you_have_no_cards_to_discard(self) -> None:
        game = create_game()
        player = game.players[0]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        drawn_card = Instant(name="Untouched Idea", owner=player, controller=player)

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        _put_on_top_of_library(game, player, drawn_card)
        _register_lorehold(game, lorehold)

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_hand(player).get_all() == []
        assert game.get_library(player).contains(drawn_card)
        assert game.get_graveyard(player).get_all() == []
