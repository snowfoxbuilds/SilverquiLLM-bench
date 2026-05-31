"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

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

ORACLE_TEXT = (
    "Flying, vigilance\n"
    "Each instant and sorcery spell you cast has casualty 1. (As you cast that "
    "spell, you may sacrifice a creature with power 1 or greater. When you do, "
    "copy the spell and you may choose new targets for the copy.)"
)


class DummyMarkedInstant(Instant):
    """Simple targeted instant used to observe casualty copies."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Marked Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
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
        self.chosen_targets[0].plus_one_counters += 1


class DummyMarkedSorcery(Sorcery):
    """Simple targeted sorcery used to verify sorceries also gain casualty."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Marked Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
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
        self.chosen_targets[0].plus_one_counters += 1


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


def _queue_choices(player, *choices) -> None:
    for choice in choices:
        player._script.append(choice)


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_legendary_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_elder_dragon_power_and_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying_and_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.keywords & Keyword.FLYING
        assert card.keywords & Keyword.VIGILANCE

    def test_rules_text(self) -> None:
        assert SilverquillTheDisputant(owner=None).rules_text == ORACLE_TEXT


class TestSilverquillTheDisputantCasualty:
    """Silverquill grants casualty 1 to your instants and sorceries."""

    def test_instant_can_resolve_without_using_casualty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        target = Creature(name="Target Bear", base_power=2, base_toughness=2)
        spell = DummyMarkedInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        silverquill.register_triggers(game)
        _queue_choices(p1, target, False)

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 1
        assert game.get_battlefield(p1).contains(fodder)

        _resolve_all(game)

        assert target.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(spell)
        assert game.get_battlefield(p1).contains(fodder)

    def test_sorcery_casualty_can_copy_spell_without_changing_targets(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        target = Creature(name="Shared Target", base_power=2, base_toughness=2)
        spell = DummyMarkedSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        silverquill.register_triggers(game)
        _queue_choices(p1, target, True, fodder, False)

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)

        _resolve_all(game)

        assert target.plus_one_counters == 2
        assert game.get_graveyard(p1).contains(spell)

    def test_casualty_copy_can_choose_new_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        first_target = Creature(name="First Target", base_power=2, base_toughness=2)
        second_target = Creature(name="Second Target", base_power=2, base_toughness=2)
        spell = DummyMarkedInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        set_board_state(game, 1, battlefield=[first_target, second_target])
        silverquill.register_triggers(game)
        _queue_choices(p1, first_target, True, fodder, True, second_target)

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2
        assert game.get_graveyard(p1).contains(fodder)

        _resolve_all(game)

        assert first_target.plus_one_counters == 1
        assert second_target.plus_one_counters == 1

    def test_casualty_cannot_be_paid_when_no_creature_has_power_one_or_greater(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        silverquill.base_power = 0
        powerless = Creature(name="Powerless Assistant", base_power=0, base_toughness=3)
        target = Creature(name="Target Bear", base_power=2, base_toughness=2)
        spell = DummyMarkedInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, powerless],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        silverquill.register_triggers(game)
        _queue_choices(p1, target, True, silverquill)

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 1
        assert game.get_battlefield(p1).contains(silverquill)
        assert game.get_battlefield(p1).contains(powerless)
        assert not game.get_graveyard(p1).contains(silverquill)
        assert not game.get_graveyard(p1).contains(powerless)

        _resolve_all(game)

        assert target.plus_one_counters == 1

    def test_creature_spells_are_not_granted_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        creature_spell = Creature(
            name="Campus Duelist",
            mana_cost=ManaCost.parse("{1}{W}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 1, ManaType.WHITE: 1},
        )
        silverquill.register_triggers(game)

        engine_cast_spell(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.get_battlefield(p1).contains(fodder)

        _resolve_all(game)

        duelists = [
            obj for obj in game.get_battlefield(p1).get_all() if getattr(obj, "name", "") == "Campus Duelist"
        ]
        assert len(duelists) == 1
        assert game.get_battlefield(p1).contains(fodder)

    def test_opponents_spells_do_not_get_casualty_from_your_silverquill(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opposing_fodder = Creature(name="Opponent Inkling", base_power=1, base_toughness=1)
        spell = DummyMarkedInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[silverquill])
        set_board_state(
            game,
            1,
            battlefield=[opposing_fodder],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        silverquill.register_triggers(game)
        _queue_choices(p2, silverquill, True, opposing_fodder)

        engine_cast_spell(game, p2, spell)

        assert len(game.stack) == 1
        assert game.get_battlefield(p2).contains(opposing_fodder)

        _resolve_all(game)

        assert silverquill.plus_one_counters == 1
        assert game.get_battlefield(p2).contains(opposing_fodder)
