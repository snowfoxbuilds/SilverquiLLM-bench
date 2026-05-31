"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from collections import deque

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class _CountermarkInstant(Instant):
    """Simple targeted instant used to observe casualty copies in tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Countermark Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if not getattr(self, "chosen_targets", None):
            return
        target = self.chosen_targets[0]
        target.plus_one_counters += 1


class _CountermarkSorcery(Sorcery):
    """Simple targeted sorcery used to observe casualty copies in tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Countermark Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if not getattr(self, "chosen_targets", None):
            return
        target = self.chosen_targets[0]
        target.plus_one_counters += 1


class _OrdinaryStudent(Creature):
    """Vanilla creature spell used to verify non-instant/sorcery spells."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Ordinary Student")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


def _creature(name: str, power: int, toughness: int) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)


def _sequential_yes_no(*answers: bool):
    queue = deque(answers)

    def _choose(_prompt: str) -> bool:
        return queue.popleft() if queue else False

    return _choose


def _sequential_targets(*targets):
    queue = deque(targets)

    def _choose(_options, _requirement):
        if not queue:
            raise AssertionError("No scripted target remains")
        return queue.popleft()

    return _choose


def _cast_silverquill(game, player_index: int, silverquill: SilverquillTheDisputant) -> None:
    player = game.players[player_index]
    engine_cast_spell(game, player, silverquill)
    _resolve_all(game)


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_legendary_elder_dragon_creature_named_and_costed(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_has_flying_vigilance_and_four_four_stats(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 to your instants and sorceries only."""

    def test_targeted_instant_can_be_copied_by_sacrificing_power_two_creature_and_retargeting(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = _CountermarkInstant(owner=p1, controller=p1)
        fodder = _creature("Silverquill Assistant", 2, 2)
        first_target = _creature("First Target", 2, 2)
        second_target = _creature("Second Target", 2, 2)

        set_board_state(
            game,
            0,
            battlefield=[fodder, first_target, second_target],
            hand=[silverquill, spell],
            mana={ManaType.COLORLESS: 10, ManaType.WHITE: 1, ManaType.BLACK: 1},
        )

        _cast_silverquill(game, 0, silverquill)

        p1.choose_yes_no = _sequential_yes_no(True, True)
        p1.choose_card = lambda cards, _description: fodder
        p1.choose_target = _sequential_targets(first_target, second_target)

        engine_cast_spell(game, p1, spell)
        _resolve_all(game)

        assert first_target.plus_one_counters == 1
        assert second_target.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)

    def test_declining_casualty_keeps_creature_and_leaves_only_original_spell_effect(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = _CountermarkInstant(owner=p1, controller=p1)
        fodder = _creature("Campus Witness", 2, 2)
        first_target = _creature("First Target", 2, 2)
        second_target = _creature("Second Target", 2, 2)

        set_board_state(
            game,
            0,
            battlefield=[fodder, first_target, second_target],
            hand=[silverquill, spell],
            mana={ManaType.COLORLESS: 10, ManaType.WHITE: 1, ManaType.BLACK: 1},
        )

        _cast_silverquill(game, 0, silverquill)

        p1.choose_yes_no = _sequential_yes_no(False)
        p1.choose_card = lambda cards, _description: fodder
        p1.choose_target = _sequential_targets(first_target)

        engine_cast_spell(game, p1, spell)
        _resolve_all(game)

        assert first_target.plus_one_counters == 1
        assert second_target.plus_one_counters == 0
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)

    def test_power_zero_creature_cannot_be_used_for_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = _CountermarkInstant(owner=p1, controller=p1)
        powerless = _creature("Powerless Witness", 0, 3)
        target = _creature("Target Creature", 2, 2)
        other_target = _creature("Other Target", 2, 2)

        set_board_state(
            game,
            0,
            battlefield=[powerless],
            hand=[silverquill, spell],
            mana={ManaType.COLORLESS: 10, ManaType.WHITE: 1, ManaType.BLACK: 1},
        )
        set_board_state(game, 1, battlefield=[target, other_target])

        _cast_silverquill(game, 0, silverquill)

        p1.choose_yes_no = _sequential_yes_no(True, True)
        p1.choose_card = lambda cards, _description: powerless
        p1.choose_target = _sequential_targets(target, other_target)

        engine_cast_spell(game, p1, spell)
        _resolve_all(game)

        assert game.get_battlefield(p1).contains(powerless)
        assert not game.get_graveyard(p1).contains(powerless)
        assert target.plus_one_counters == 1
        assert other_target.plus_one_counters == 0

    def test_targeted_sorcery_also_gets_casualty_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = _CountermarkSorcery(owner=p1, controller=p1)
        fodder = _creature("Class Scribe", 1, 1)
        first_target = _creature("First Target", 2, 2)
        second_target = _creature("Second Target", 2, 2)

        set_board_state(
            game,
            0,
            battlefield=[fodder, first_target, second_target],
            hand=[silverquill, spell],
            mana={ManaType.COLORLESS: 10, ManaType.WHITE: 1, ManaType.BLACK: 1},
        )

        _cast_silverquill(game, 0, silverquill)

        p1.choose_yes_no = _sequential_yes_no(True, True)
        p1.choose_card = lambda cards, _description: fodder
        p1.choose_target = _sequential_targets(first_target, second_target)

        engine_cast_spell(game, p1, spell)
        _resolve_all(game)

        assert first_target.plus_one_counters == 1
        assert second_target.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(fodder)

    def test_opponents_instants_and_sorceries_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = _CountermarkInstant(owner=p2, controller=p2)
        fodder = _creature("Opponent Fodder", 2, 2)
        target = _creature("Target Creature", 2, 2)
        untouched = _creature("Untouched Creature", 2, 2)

        set_board_state(
            game,
            0,
            hand=[silverquill],
            mana={ManaType.COLORLESS: 10, ManaType.WHITE: 1, ManaType.BLACK: 1},
        )
        set_board_state(
            game,
            1,
            battlefield=[fodder, target, untouched],
            hand=[spell],
            mana={ManaType.COLORLESS: 10},
        )

        _cast_silverquill(game, 0, silverquill)

        p2.choose_yes_no = _sequential_yes_no(True, True)
        p2.choose_card = lambda cards, _description: fodder
        p2.choose_target = _sequential_targets(target, untouched)

        engine_cast_spell(game, p2, spell)
        _resolve_all(game)

        assert target.plus_one_counters == 1
        assert untouched.plus_one_counters == 0
        assert game.get_battlefield(p2).contains(fodder)
        assert not game.get_graveyard(p2).contains(fodder)

    def test_noninstant_and_nonsorcery_spells_you_cast_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        creature_spell = _OrdinaryStudent(owner=p1, controller=p1)
        fodder = _creature("Campus Assistant", 2, 2)

        set_board_state(
            game,
            0,
            battlefield=[fodder],
            hand=[silverquill, creature_spell],
            mana={ManaType.COLORLESS: 10, ManaType.WHITE: 1, ManaType.BLACK: 1},
        )

        _cast_silverquill(game, 0, silverquill)

        p1.choose_yes_no = _sequential_yes_no(True)
        p1.choose_card = lambda cards, _description: fodder

        engine_cast_spell(game, p1, creature_spell)
        _resolve_all(game)

        students = [
            card for card in game.get_battlefield(p1).get_all() if card.name == "Ordinary Student"
        ]

        assert len(students) == 1
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
