"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from types import MethodType

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as cast_spell_to_stack
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype, TargetRequirement, Zone
from test_utils import create_game, set_board_state


def _bind_choose_yes_no(player, answers: list[bool]) -> None:
    remaining = iter(answers)

    def choose_yes_no(self, prompt: str) -> bool:
        return next(remaining)

    player.choose_yes_no = MethodType(choose_yes_no, player)


def _bind_choose(player, answers: list[object]) -> None:
    remaining = iter(answers)

    def choose(self, options, description: str):
        return next(remaining)

    player.choose = MethodType(choose, player)


def _bind_choose_card(player, chosen_card) -> None:
    def choose_card(self, cards, description: str):
        assert chosen_card in cards
        return chosen_card

    player.choose_card = MethodType(choose_card, player)


def _bind_choose_target(player, chosen_targets: list[object]) -> None:
    remaining = iter(chosen_targets)

    def choose_target(self, options, requirement):
        return next(remaining)

    player.choose_target = MethodType(choose_target, player)


def _set_main_phase(game) -> None:
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0


def _resolve_entire_stack(game) -> None:
    while not game.stack.is_empty():
        stack_object = game.stack.pop()
        stack_object.on_resolve(game)


class _CountingInstant(Instant):
    def __init__(self, recorder: dict[str, int], **kwargs) -> None:
        kwargs.setdefault("name", "Counting Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)
        self.recorder = recorder

    def on_resolve(self, game) -> None:
        self.recorder["count"] += 1


class _CountingSorcery(Sorcery):
    def __init__(self, recorder: dict[str, int], **kwargs) -> None:
        kwargs.setdefault("name", "Counting Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)
        self.recorder = recorder

    def on_resolve(self, game) -> None:
        self.recorder["count"] += 1


class _MarkedLesson(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Marked Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        chosen_targets = getattr(self, "chosen_targets", [])
        if chosen_targets:
            chosen_targets[0].plus_one_counters += 1


class TestSilverquillTheDisputantProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_has_flying_vigilance_and_four_four_stats(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestSilverquillTheDisputantCasualty:
    """Battlefield casualty-granting contract."""

    def test_you_may_decline_casualty_and_cast_only_the_original_spell(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        recorder = {"count": 0}
        spell = _CountingInstant(recorder, owner=p1, controller=p1)

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        silverquill.register_triggers(game)
        _bind_choose_yes_no(p1, [False])
        _bind_choose(p1, [False])

        cast_spell_to_stack(game, p1, spell)
        _resolve_entire_stack(game)

        assert recorder["count"] == 1
        assert game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(spell)

    def test_grants_casualty_to_your_instant_spell_when_you_sacrifice_a_power_one_creature(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        recorder = {"count": 0}
        spell = _CountingInstant(recorder, owner=p1, controller=p1)

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        silverquill.register_triggers(game)
        _bind_choose_yes_no(p1, [True])
        _bind_choose(p1, [True])
        _bind_choose_card(p1, fodder)

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack) == 2
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)

        _resolve_entire_stack(game)

        assert recorder["count"] == 2
        assert game.get_graveyard(p1).contains(spell)

    def test_grants_casualty_to_your_sorcery_spell_too(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Student", base_power=2, base_toughness=2)
        recorder = {"count": 0}
        spell = _CountingSorcery(recorder, owner=p1, controller=p1)

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        silverquill.register_triggers(game)
        _bind_choose_yes_no(p1, [True])
        _bind_choose(p1, [True])
        _bind_choose_card(p1, fodder)

        cast_spell_to_stack(game, p1, spell)
        _resolve_entire_stack(game)

        assert recorder["count"] == 2
        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(spell)

    def test_does_not_grant_casualty_to_creature_spells(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        creature_spell = Creature(
            name="Ordinary Student",
            mana_cost=ManaCost.parse("{1}{W}"),
            base_power=2,
            base_toughness=2,
        )

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[creature_spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        silverquill.register_triggers(game)
        _bind_choose_yes_no(p1, [True])
        _bind_choose(p1, [True])
        _bind_choose_card(p1, fodder)

        cast_spell_to_stack(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)

    def test_only_spells_you_cast_get_casualty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opponent_fodder = Creature(name="Opponent Inkling", base_power=1, base_toughness=1)
        recorder = {"count": 0}
        opponent_spell = _CountingInstant(recorder, owner=p2, controller=p2)

        _set_main_phase(game)
        set_board_state(game, 0, battlefield=[silverquill])
        set_board_state(
            game,
            1,
            battlefield=[opponent_fodder],
            hand=[opponent_spell],
            mana={ManaType.BLACK: 1},
        )
        silverquill.register_triggers(game)
        _bind_choose_yes_no(p2, [True])
        _bind_choose(p2, [True])
        _bind_choose_card(p2, opponent_fodder)

        cast_spell_to_stack(game, p2, opponent_spell)
        _resolve_entire_stack(game)

        assert recorder["count"] == 1
        assert game.get_battlefield(p2).contains(opponent_fodder)
        assert not game.get_graveyard(p2).contains(opponent_fodder)

    def test_casualty_requires_a_creature_with_power_one_or_greater(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        wall = Creature(name="Silent Wall", base_power=0, base_toughness=4)
        recorder = {"count": 0}
        spell = _CountingInstant(recorder, owner=p1, controller=p1)

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, wall],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        silverquill.register_triggers(game)
        _bind_choose_yes_no(p1, [True])
        _bind_choose(p1, [True])
        _bind_choose_card(p1, wall)

        cast_spell_to_stack(game, p1, spell)
        _resolve_entire_stack(game)

        assert recorder["count"] == 1
        assert game.get_battlefield(p1).contains(wall)
        assert not game.get_graveyard(p1).contains(wall)

    def test_copy_may_choose_new_targets(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        ally = Creature(name="Ally", base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", base_power=2, base_toughness=2)
        spell = _MarkedLesson(owner=p1, controller=p1)

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder, ally],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(game, 1, battlefield=[enemy])
        silverquill.register_triggers(game)
        _bind_choose_yes_no(p1, [True, True])
        _bind_choose(p1, [True, True])
        _bind_choose_card(p1, fodder)
        _bind_choose_target(p1, [enemy, ally])

        cast_spell_to_stack(game, p1, spell)
        _resolve_entire_stack(game)

        assert enemy.plus_one_counters == 1
        assert ally.plus_one_counters == 1
