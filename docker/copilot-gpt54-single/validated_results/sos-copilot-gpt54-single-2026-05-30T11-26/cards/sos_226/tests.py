"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.casting import cast_spell as cast_spell_to_stack
from engine.card import Creature, Instant, Sorcery
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Color, Keyword, ManaCost, ManaType, Phase, Supertype, TargetRequirement, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _set_precombat_main(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _creature(name: str, owner, power: int, toughness: int) -> Creature:
    return Creature(
        name=name,
        owner=owner,
        controller=owner,
        base_power=power,
        base_toughness=toughness,
    )


class _SilverquillLesson(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Silverquill Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 2


class _SilverquillLecture(Sorcery):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Silverquill Lecture")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 3


class _TargetedRebuke(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Targeted Rebuke")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if getattr(self, "chosen_targets", None):
            self.chosen_targets[0].damage_marked += 1


class TestSilverquillTheDisputantProperties:
    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Silverquill, the Disputant"
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_has_white_black_cost_flying_vigilance_and_four_four_stats(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.colors == {Color.WHITE, Color.BLACK}
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestSilverquillTheDisputantCasualty:
    def test_instant_resolves_once_when_you_decline_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Eager Student", p1, 2, 2)
        spell = _SilverquillLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        silverquill.register_triggers(game)
        p1.choose_yes_no = lambda _prompt: False

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert p1.life == 22
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(spell)

    def test_casualty_sacrifices_a_power_two_creature_and_copies_an_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Inkling Assistant", p1, 2, 2)
        spell = _SilverquillLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        silverquill.register_triggers(game)
        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda _cards, _description: fodder

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert p1.life == 24
        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.total() == 0

    def test_casualty_also_copies_sorcery_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Ink-Tipped Adept", p1, 1, 1)
        spell = _SilverquillLecture(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        silverquill.register_triggers(game)
        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda _cards, _description: fodder
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert p1.life == 26
        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(spell)

    def test_copy_may_choose_new_targets(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Debate Clerk", p1, 1, 1)
        first_target = _creature("First Witness", p2, 2, 2)
        second_target = _creature("Second Witness", p2, 2, 2)
        spell = _TargetedRebuke(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, fodder], hand=[spell], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[first_target, second_target])
        silverquill.register_triggers(game)
        decisions = iter([True, True])
        targets = iter([first_target, second_target])
        p1.choose_yes_no = lambda _prompt: next(decisions)
        p1.choose_card = lambda _cards, _description: fodder
        p1.choose_target = lambda _options, _requirement: next(targets)

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert first_target.damage_marked == 1
        assert second_target.damage_marked == 1
        assert game.get_graveyard(p1).contains(fodder)

    def test_zero_power_creature_cannot_be_sacrificed_for_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        wall = _creature("Silent Wall", p1, 0, 4)
        spell = _SilverquillLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, wall],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        silverquill.register_triggers(game)
        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda _cards, _description: wall

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert p1.life == 22
        assert game.get_battlefield(p1).contains(wall)
        assert not game.get_graveyard(p1).contains(wall)

    def test_only_your_spells_get_casualty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        your_fodder = _creature("Your Assistant", p1, 2, 2)
        opponent_fodder = _creature("Borrowed Notes", p2, 2, 2)
        your_spell = _SilverquillLesson(owner=p1, controller=p1)
        opponent_spell = _SilverquillLesson(owner=p2, controller=p2)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, your_fodder],
            hand=[your_spell],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[opponent_fodder],
            hand=[opponent_spell],
            mana={ManaType.WHITE: 1},
        )
        silverquill.register_triggers(game)
        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda _cards, _description: your_fodder
        p2.choose_yes_no = lambda _prompt: True
        p2.choose_card = lambda _cards, _description: opponent_fodder

        cast_spell_to_stack(game, p1, your_spell)
        _resolve_all(game)
        cast_spell_to_stack(game, p2, opponent_spell)
        _resolve_all(game)

        assert p1.life == 24
        assert game.get_graveyard(p1).contains(your_fodder)
        assert p2.life == 22
        assert game.get_battlefield(p2).contains(opponent_fodder)
        assert not game.get_graveyard(p2).contains(opponent_fodder)
