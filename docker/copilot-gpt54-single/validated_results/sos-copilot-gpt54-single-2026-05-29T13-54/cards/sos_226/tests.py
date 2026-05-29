"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.casting import cast_spell as engine_cast_spell
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class _LessonInConflict(Instant):
    """Simple targeted instant used to exercise casualty copying."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Lesson in Conflict")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
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
        chosen = getattr(self, "chosen_targets", None) or []
        if not chosen:
            return
        chosen[0].damage_marked += 1


class _ClosingArgument(Sorcery):
    """Simple sorcery used to verify Silverquill grants casualty to sorceries."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Closing Argument")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.life += 1


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying_and_vigilance(self) -> None:
        keywords = SilverquillTheDisputant(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.VIGILANCE in keywords


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 to your instants and sorceries."""

    @staticmethod
    def _resolve_all(game) -> None:
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    @staticmethod
    def _creature(name: str, *, power: int, toughness: int) -> Creature:
        return Creature(name=name, base_power=power, base_toughness=toughness)

    def test_casualty_paid_copies_an_instant_and_allows_new_targets(self, monkeypatch) -> None:
        game = create_game()
        p1, p2 = game.players
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = self._creature("Inkling Witness", power=1, toughness=1)
        first_target = self._creature("First Student", power=3, toughness=3)
        second_target = self._creature("Second Student", power=3, toughness=3)
        spell = _LessonInConflict(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[dragon, fodder],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        set_board_state(game, 1, battlefield=[first_target, second_target])
        dragon.register_triggers(game)

        target_choices = iter([first_target, second_target])
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: fodder)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: next(target_choices))

        engine_cast_spell(game, p1, spell)
        self._resolve_all(game)

        assert game.get_graveyard(p1).contains(fodder) is True
        assert game.get_battlefield(p1).contains(fodder) is False
        assert first_target.damage_marked == 1
        assert second_target.damage_marked == 1
        assert game.get_graveyard(p1).contains(spell) is True

    def test_declining_casualty_leaves_the_spell_uncopied(self, monkeypatch) -> None:
        game = create_game()
        p1, p2 = game.players
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = self._creature("Inkling Witness", power=1, toughness=1)
        target = self._creature("Only Student", power=3, toughness=3)
        spell = _LessonInConflict(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[dragon, fodder],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        dragon.register_triggers(game)

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: target)

        engine_cast_spell(game, p1, spell)
        self._resolve_all(game)

        assert game.get_battlefield(p1).contains(fodder) is True
        assert game.get_graveyard(p1).contains(fodder) is False
        assert target.damage_marked == 1

    def test_power_zero_creatures_cannot_be_used_for_casualty(self, monkeypatch) -> None:
        game = create_game()
        p1, p2 = game.players
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        weakling = self._creature("Meek Witness", power=0, toughness=2)
        target = self._creature("Target Student", power=3, toughness=3)
        spell = _LessonInConflict(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[dragon, weakling],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        dragon.register_triggers(game)

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: weakling)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: target)

        engine_cast_spell(game, p1, spell)
        self._resolve_all(game)

        assert game.get_battlefield(p1).contains(weakling) is True
        assert game.get_graveyard(p1).contains(weakling) is False
        assert target.damage_marked == 1

    def test_casualty_also_applies_to_sorcery_spells(self, monkeypatch) -> None:
        game = create_game(player1_life=10)
        p1 = game.players[0]
        dragon = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = self._creature("Inkling Witness", power=1, toughness=1)
        spell = _ClosingArgument(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[dragon, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        dragon.register_triggers(game)
        game.active_player = p1
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN

        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: fodder)

        engine_cast_spell(game, p1, spell)
        self._resolve_all(game)

        assert p1.life == 12
        assert game.get_graveyard(p1).contains(fodder) is True
        assert game.get_battlefield(p1).contains(fodder) is False
