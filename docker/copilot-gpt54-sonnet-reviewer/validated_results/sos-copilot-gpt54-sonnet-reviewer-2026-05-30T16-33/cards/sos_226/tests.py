"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell
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


class _CasualtyTestPing(Instant):
    """Minimal targeted instant for casualty copy tests."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Test Ping")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return
        targets[0].life -= 1


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_a_legendary_elder_dragon_with_flying_vigilance_and_four_four(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_name_mana_cost_and_rules_text_match_the_spec(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.rules_text == (
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power "
            "1 or greater. When you do, copy the spell and you may choose "
            "new targets for the copy.)"
        )


class TestSilverquillTheDisputantCasualtyGrant:
    """Silverquill should grant casualty 1 to the right spells only."""

    def test_exposes_casualty_metadata_with_amount_one_and_minimum_power_one(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert "Casualty" in getattr(card, "mechanic_keywords", set())
        casualty_metadata = getattr(card, "keyword_metadata", {}).get("Casualty")
        assert casualty_metadata is not None
        assert casualty_metadata.get("amount") == 1
        assert casualty_metadata.get("minimum_power") == 1

    def test_grants_casualty_one_to_your_instant_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = Instant(name="Debate Brief")
        set_board_state(game, 0, battlefield=[card])

        assert card.get_casualty_value_for(game, p1, spell) == 1

    def test_grants_casualty_one_to_your_sorcery_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = Sorcery(name="Closing Argument")
        set_board_state(game, 0, battlefield=[card])

        assert card.get_casualty_value_for(game, p1, spell) == 1

    def test_does_not_grant_casualty_to_noninstant_nonsorcery_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = Creature(name="Campus Witness", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])

        assert card.get_casualty_value_for(game, p1, spell) is None

    def test_does_not_grant_casualty_to_an_opponents_instant_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = Instant(name="Opponent's Rebuttal", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[card])

        assert card.get_casualty_value_for(game, p2, spell) is None

    def test_does_not_grant_casualty_while_not_on_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = Instant(name="Absent-Minded Rebuttal")
        set_board_state(game, 0, hand=[card])

        assert card.get_casualty_value_for(game, p1, spell) is None


class TestSilverquillTheDisputantCasualtyCasting:
    """Granted casualty should work through the public casting pipeline."""

    @staticmethod
    def _set_script(player: Any, *choices: Any) -> None:
        player._script.clear()
        player._script.extend(choices)

    def test_paid_casualty_sacrifices_the_creature_adds_a_copy_and_keeps_original_target_when_not_retargeted(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling Assistant",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = _CasualtyTestPing(owner=p1, controller=p1)
        self._set_script(p1, p2, True, fodder, False)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )

        cast_spell(game, p1, spell)

        assert game.get_battlefield(p1).contains(fodder) is False
        assert game.get_graveyard(p1).contains(fodder) is True
        assert len(game.stack) == 2
        stack_objects = game.stack.objects()
        assert stack_objects[0].metadata.get("copy_reason") == "casualty"
        assert stack_objects[0].source is not spell
        assert stack_objects[1].source is spell

        game.stack.pop().on_resolve(game)
        game.stack.pop().on_resolve(game)

        assert p2.life == 18
        assert game.get_graveyard(p1).contains(spell) is True

    def test_paid_casualty_can_choose_new_targets_for_the_copy(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling Assistant",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = _CasualtyTestPing(owner=p1, controller=p1)
        self._set_script(p1, p2, True, fodder, True, p1)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )

        cast_spell(game, p1, spell)

        top = game.stack.peek()
        assert top is not None
        assert top.targets == [p1]

        game.stack.pop().on_resolve(game)
        game.stack.pop().on_resolve(game)

        assert p1.life == 19
        assert p2.life == 19

    def test_declining_casualty_casts_only_the_original_spell_without_sacrificing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling Assistant",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = _CasualtyTestPing(owner=p1, controller=p1)
        self._set_script(p1, p2, False)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )

        cast_spell(game, p1, spell)

        assert game.get_battlefield(p1).contains(fodder) is True
        assert game.get_graveyard(p1).contains(fodder) is False
        assert len(game.stack) == 1

        game.stack.pop().on_resolve(game)

        assert p2.life == 19

    def test_casualty_candidates_exclude_creatures_below_power_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        weakling = Creature(
            name="Tiny Witness",
            owner=p1,
            controller=p1,
            base_power=0,
            base_toughness=1,
        )
        spell = _CasualtyTestPing(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[silverquill, weakling],
            hand=[spell],
        )

        offers = game.get_casualty_offers(p1, spell)
        candidates = game.get_casualty_candidates(p1, offers[0]["minimum_power"])

        assert weakling not in candidates
        assert silverquill in candidates
