"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


class PracticeBolt(Instant):
    """Simple targeted instant used to verify casualty copying."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Practice Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
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
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return
        target = targets[0]
        if target is None:
            return
        target.damage_marked += 1


class StudyBreak(Sorcery):
    """Simple untargeted sorcery used to verify casualty copying."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Study Break")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 1


class TestSilverquillTheDisputantProperties:
    """Static card data should match the card spec."""

    def test_is_a_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_is_a_legendary_elder_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_power_and_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying_and_vigilance(self) -> None:
        keywords = SilverquillTheDisputant(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.VIGILANCE in keywords


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 to your instants and sorceries."""

    @staticmethod
    def _put_on_battlefield_and_register(game, player_index: int, permanents: list[Any]) -> None:
        set_board_state(game, player_index, battlefield=permanents)
        for permanent in permanents:
            permanent.register_triggers(game)
            permanent.register_replacement_effects(game)

    def test_sacrificing_a_power_one_creature_copies_a_targeted_instant_and_allows_new_targets(self, monkeypatch) -> None:
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
        first_target = Creature(
            name="First Target",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        second_target = Creature(
            name="Second Target",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        spell = PracticeBolt(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, 0, [silverquill, fodder])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.RED: 1},
        )
        set_board_state(game, 1, battlefield=[first_target, second_target])

        target_calls = {"count": 0}

        def choose_target(options, requirement):
            if isinstance(options, list) and fodder in options:
                return fodder
            if getattr(requirement, "description", "") == "target creature":
                target_calls["count"] += 1
                return first_target if target_calls["count"] == 1 else second_target
            return first_target

        def choose_card(cards, description):
            return fodder if fodder in cards else cards[0]

        def choose(options, description):
            if isinstance(options, list) and fodder in options:
                return fodder
            if isinstance(options, list) and second_target in options:
                return second_target
            return options[0] if options else None

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_target", choose_target)
        monkeypatch.setattr(p1, "choose_card", choose_card)
        monkeypatch.setattr(p1, "choose", choose)

        cast_spell(game, 0, "Practice Bolt")

        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_battlefield(p1).contains(fodder) is False
        assert first_target.damage_marked == 1
        assert second_target.damage_marked == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_sacrificing_a_power_one_creature_copies_a_sorcery(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling Student",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = StudyBreak(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, 0, [silverquill, fodder])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: fodder)
        monkeypatch.setattr(p1, "choose", lambda options, description: fodder if fodder in options else options[0])

        cast_spell(game, 0, "Study Break")

        assert p1.life == 22
        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_battlefield(p1).contains(fodder) is False
        assert game.get_graveyard(p1).contains(spell)

    def test_creatures_with_power_zero_are_not_eligible_for_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        wall = Creature(
            name="Wall of Notes",
            owner=p1,
            controller=p1,
            base_power=0,
            base_toughness=4,
        )
        spell = StudyBreak(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, 0, [silverquill, wall])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Study Break")

        assert p1.life == 21
        assert game.get_battlefield(p1).contains(wall)
        assert game.get_graveyard(p1).contains(wall) is False

    def test_only_your_instants_and_sorceries_get_casualty(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opposing_fodder = Creature(
            name="Opponent Fodder",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        first_target = Creature(
            name="First Target",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        second_target = Creature(
            name="Second Target",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        spell = PracticeBolt(owner=p2, controller=p2)

        self._put_on_battlefield_and_register(game, 0, [silverquill])
        set_board_state(game, 0, battlefield=[silverquill, first_target, second_target])
        set_board_state(
            game,
            1,
            battlefield=[opposing_fodder],
            hand=[spell],
            mana={ManaType.RED: 1},
        )

        target_calls = {"count": 0}

        def choose_target(options, requirement):
            if isinstance(options, list) and opposing_fodder in options:
                return opposing_fodder
            if getattr(requirement, "description", "") == "target creature":
                target_calls["count"] += 1
                return first_target if target_calls["count"] == 1 else second_target
            return first_target

        monkeypatch.setattr(p2, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p2, "choose_target", choose_target)
        monkeypatch.setattr(
            p2,
            "choose_card",
            lambda cards, description: opposing_fodder if opposing_fodder in cards else cards[0],
        )
        monkeypatch.setattr(
            p2,
            "choose",
            lambda options, description: opposing_fodder if opposing_fodder in options else options[0],
        )

        cast_spell(game, 1, "Practice Bolt")

        assert first_target.damage_marked == 1
        assert second_target.damage_marked == 0
        assert game.get_battlefield(p2).contains(opposing_fodder)
        assert game.get_graveyard(p2).contains(opposing_fodder) is False
