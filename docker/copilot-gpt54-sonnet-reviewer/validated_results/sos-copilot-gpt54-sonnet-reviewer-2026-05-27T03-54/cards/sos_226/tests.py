"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestPointedRebuke(Instant):
    """Simple targeted instant used to verify casualty-copy behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Pointed Rebuke")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        chosen = getattr(self, "chosen_targets", [])
        target = chosen[0] if chosen else None
        if target is not None:
            target.life -= 2


class TestClosingArgument(Sorcery):
    """Simple targeted sorcery used to verify casualty-copy behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Closing Argument")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        chosen = getattr(self, "chosen_targets", [])
        target = chosen[0] if chosen else None
        if target is not None:
            target.life -= 2


def _register_silverquill(game, silverquill: SilverquillTheDisputant) -> None:
    """Register Silverquill's static ability and apply continuous effects."""
    silverquill.register_triggers(game)
    silverquill.register_replacement_effects(game)
    game.effect_manager.apply_all(game)


def _cast_from_hand(game, player_index: int, card) -> None:
    """Cast *card* from hand without auto-resolving it."""
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = player_index
    game.priority_player_index = player_index
    engine_cast_spell(game, game.players[player_index], card)


def _resolve_all(game) -> None:
    """Resolve everything currently on the stack."""
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestSilverquillTheDisputantProperties:
    """Static characteristics should match the SOS 226 spec."""

    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Silverquill, the Disputant"
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_has_expected_cost_colors_keywords_and_stats(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.colors == {Color.WHITE, Color.BLACK}
        assert card.color_identity == {Color.WHITE, Color.BLACK}
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4
        assert card.rules_text == (
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. (As you cast "
            "that spell, you may sacrifice a creature with power 1 or greater. "
            "When you do, copy the spell and you may choose new targets for the copy.)"
        )


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 only to your instants and sorceries."""

    def test_your_sorcery_can_be_copied_by_sacrificing_a_power_one_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling Student",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = TestClosingArgument(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2},
        )
        _register_silverquill(game, silverquill)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder if fodder in cards else None
        p1.choose_target = lambda options, requirement: p2

        _cast_from_hand(game, 0, spell)
        _resolve_all(game)

        assert p2.life == 16
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)
        assert [obj.name for obj in game.get_graveyard(p1).get_all()].count("Closing Argument") == 1

    def test_casualty_copy_may_choose_a_new_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Campus Familiar",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = TestPointedRebuke(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        _register_silverquill(game, silverquill)

        target_calls = {"count": 0}

        def _choose_target(options, requirement):
            target_calls["count"] += 1
            return p2 if target_calls["count"] == 1 else p1

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder if fodder in cards else None
        p1.choose_target = _choose_target

        _cast_from_hand(game, 0, spell)
        _resolve_all(game)

        assert p1.life == 18
        assert p2.life == 18
        assert [obj.name for obj in game.get_graveyard(p1).get_all()].count("Pointed Rebuke") == 1

    def test_zero_power_creatures_cannot_pay_the_casualty_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        wall = Creature(
            name="Study Wall",
            owner=p1,
            controller=p1,
            base_power=0,
            base_toughness=4,
        )
        spell = TestPointedRebuke(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, wall],
            hand=[spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        _register_silverquill(game, silverquill)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: wall if wall in cards else None
        p1.choose_target = lambda options, requirement: p2

        _cast_from_hand(game, 0, spell)
        _resolve_all(game)

        assert p2.life == 18
        assert game.get_battlefield(p1).contains(wall)
        assert not game.get_graveyard(p1).contains(wall)
        assert [obj.name for obj in game.get_graveyard(p1).get_all()].count("Pointed Rebuke") == 1

    def test_creature_spells_you_cast_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Eager Pupil",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        creature_spell = Creature(
            name="Silverquill Trainee",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 2},
        )
        _register_silverquill(game, silverquill)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder if fodder in cards else None

        _cast_from_hand(game, 0, creature_spell)
        _resolve_all(game)

        battlefield_names = [obj.name for obj in game.get_battlefield(p1).get_all()]
        assert battlefield_names.count("Silverquill Trainee") == 1
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)

    def test_opponents_instants_and_sorceries_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        enemy_fodder = Creature(
            name="Opponent's Assistant",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        spell = TestPointedRebuke(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[silverquill])
        set_board_state(
            game,
            1,
            battlefield=[enemy_fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        _register_silverquill(game, silverquill)

        p2.choose_yes_no = lambda prompt: True
        p2.choose_card = lambda cards, description: enemy_fodder if enemy_fodder in cards else None
        p2.choose_target = lambda options, requirement: p1

        _cast_from_hand(game, 1, spell)
        _resolve_all(game)

        assert p1.life == 18
        assert game.get_battlefield(p2).contains(enemy_fodder)
        assert not game.get_graveyard(p2).contains(enemy_fodder)
        assert [obj.name for obj in game.get_graveyard(p2).get_all()].count("Pointed Rebuke") == 1
