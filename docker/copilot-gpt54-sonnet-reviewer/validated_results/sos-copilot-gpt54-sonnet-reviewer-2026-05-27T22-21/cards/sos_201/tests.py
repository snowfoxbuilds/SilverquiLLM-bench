"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell_for_miracle, resolve_top
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Color, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


class TrainingSpell(Sorcery):
    """Simple spell used for discard and draw tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)


class TrainingInstant(Instant):
    """Simple instant used for miracle-grant tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_name_and_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_is_legendary_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_red_white_colors(self) -> None:
        assert LoreholdTheHistorian(owner=None).colors == {Color.RED, Color.WHITE}

    def test_has_flying_and_haste(self) -> None:
        keywords = LoreholdTheHistorian(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.HASTE in keywords


class TestLoreholdTheHistorianMiracle:
    """Lorehold should grant and enable miracle {2} for hand spells."""

    def test_grants_miracle_two_to_instants_and_sorceries_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        instant_card = TrainingInstant(owner=p1, controller=p1)
        sorcery_card = TrainingSpell(owner=p1, controller=p1)
        creature_card = Creature(
            name="Training Creature",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{R}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[instant_card, sorcery_card, creature_card],
        )

        assert instant_card.has_miracle(game) is True
        assert instant_card.get_miracle_cost(game) == ManaCost.parse("{2}")
        assert sorcery_card.has_miracle(game) is True
        assert sorcery_card.get_miracle_cost(game) == ManaCost.parse("{2}")
        assert creature_card.has_miracle(game) is False
        assert creature_card.get_miracle_cost(game) is None

    def test_first_drawn_spell_opens_miracle_window(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_spell = TrainingSpell(name="Miracle Lesson", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        p1.zones[Zone.LIBRARY].add(drawn_spell)
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        game.reset_turn_draw_tracking()

        draw_card(game, p1)
        window = game.get_miracle_window(drawn_spell)

        assert p1.zones[Zone.HAND].contains(drawn_spell)
        assert game.has_miracle_window(drawn_spell) is True
        assert window is not None
        assert window.player is p1
        assert drawn_spell.can_cast_for_miracle(game, p1) is True
        assert drawn_spell.get_miracle_cost(game) == ManaCost.parse("{2}")

    def test_second_card_drawn_this_turn_does_not_open_miracle_window(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = Creature(
            name="First Draw",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )
        second_draw = TrainingSpell(name="Second Draw Spell", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        p1.zones[Zone.LIBRARY].add(second_draw)
        p1.zones[Zone.LIBRARY].add(first_draw)
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        game.reset_turn_draw_tracking()

        draw_card(game, p1)
        draw_card(game, p1)

        assert p1.zones[Zone.HAND].contains(second_draw)
        assert game.has_miracle_window(second_draw) is False
        assert second_draw.can_cast_for_miracle(game, p1) is False

    def test_cast_spell_for_miracle_uses_two_mana_and_closes_window(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_spell = TrainingSpell(
            name="Expensive Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{5}"),
        )

        set_board_state(game, 0, battlefield=[lorehold], hand=[], mana={})
        p1.zones[Zone.LIBRARY].add(drawn_spell)
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        game.reset_turn_draw_tracking()

        draw_card(game, p1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        cast_spell_for_miracle(game, p1, drawn_spell)

        assert not p1.zones[Zone.HAND].contains(drawn_spell)
        assert game.stack.peek().source is drawn_spell
        assert drawn_spell.alternate_cost_paid == "miracle"
        assert drawn_spell.mana_spent_to_cast == 2
        assert p1.mana_pool.total() == 0
        assert game.has_miracle_window(drawn_spell) is False

        resolve_top(game)

        assert p1.zones[Zone.GRAVEYARD].contains(drawn_spell)


class TestLoreholdTheHistorianUpkeepTrigger:
    """The upkeep trigger should let you loot on each opponent's upkeep."""

    def test_registers_one_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())

        assert after - before == 1
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        assert trigger.event_type is BeginningOfUpkeepTriggeredEvent
        assert trigger.controller is p1

    def test_does_not_trigger_on_your_own_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 1
        game.active_player_index = 0
        game.priority_player_index = 0

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_you_may_decline_the_opponent_upkeep_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        hand_card = TrainingSpell(name="Keep Me", owner=p1, controller=p1)
        library_card = TrainingSpell(name="Still In Library", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[hand_card])
        p1.zones[Zone.LIBRARY].add(library_card)
        card.register_triggers(game)
        p1.choose_yes_no = lambda prompt: False
        game.active_player_index = 1
        game.priority_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        resolve_top(game)

        assert p1.zones[Zone.HAND].contains(hand_card)
        assert not p1.zones[Zone.HAND].contains(library_card)
        assert p1.zones[Zone.LIBRARY].contains(library_card)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert p2.zones[Zone.HAND].get_all() == []

    def test_opponent_upkeep_trigger_discards_then_draws(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_card = TrainingSpell(name="Discard Me", owner=p1, controller=p1)
        draw_into_hand = TrainingSpell(name="Draw Me", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[discard_card])
        p1.zones[Zone.LIBRARY].add(draw_into_hand)
        card.register_triggers(game)
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: discard_card
        game.active_player_index = 1
        game.priority_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        assert game.stack.peek().source is card

        resolve_top(game)

        assert p1.zones[Zone.GRAVEYARD].contains(discard_card)
        assert not p1.zones[Zone.HAND].contains(discard_card)
        assert p1.zones[Zone.HAND].contains(draw_into_hand)
        assert not p1.zones[Zone.LIBRARY].contains(draw_into_hand)

    def test_opponent_upkeep_trigger_with_empty_hand_does_not_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        library_card = TrainingSpell(name="Not Drawn", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[])
        p1.zones[Zone.LIBRARY].add(library_card)
        card.register_triggers(game)
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: None
        game.active_player_index = 1
        game.priority_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        resolve_top(game)

        assert p1.zones[Zone.LIBRARY].contains(library_card)
        assert not p1.zones[Zone.HAND].contains(library_card)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
