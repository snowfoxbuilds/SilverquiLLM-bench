"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as cast_without_resolution
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


class DisputedBolt(Instant):
    """Simple targeted instant used to verify casualty copies and retargeting."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Disputed Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game) -> list[TargetRequirement]:
        del game
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        del game
        target = getattr(self, "chosen_targets", [None])[0]
        if target is not None:
            target.damage_marked += 1


class DebateNotes(Sorcery):
    """Simple untargeted sorcery used to verify granted casualty on sorceries."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Debate Notes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        del game
        controller = self.controller
        controller.sos_226_resolution_count = getattr(controller, "sos_226_resolution_count", 0) + 1


def _set_main_phase(game, player_index: int) -> None:
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestSilverquillTheDisputantProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_elder_dragon_creature_with_specified_stats(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Silverquill, the Disputant"
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying_and_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_is_white_and_black(self) -> None:
        assert SilverquillTheDisputant(owner=None).colors == {Color.WHITE, Color.BLACK}


class TestSilverquillTheDisputantCasualty:
    """Silverquill grants casualty 1 to your instant and sorcery spells."""

    def test_your_targeted_instant_can_be_copied_by_sacrificing_a_power_one_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        casualty_fodder = Creature(name="Inkling", base_power=1, base_toughness=1)
        first_target = Creature(name="First Target", base_power=2, base_toughness=2)
        second_target = Creature(name="Second Target", base_power=2, base_toughness=2)
        spell = DisputedBolt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, casualty_fodder, first_target, second_target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        _set_main_phase(game, 0)

        assert spell.get_casualty_value(game, p1) == 1

        chosen_targets = iter([first_target, second_target])
        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda cards, _description: casualty_fodder
        p1.choose_target = lambda _options, _requirement: next(chosen_targets)

        cast_without_resolution(game, p1, spell)

        assert game.get_graveyard(p1).contains(casualty_fodder)
        assert not game.get_battlefield(p1).contains(casualty_fodder)
        assert len(game.stack.objects()) == 2
        assert {obj.source.name for obj in game.stack.objects()} == {"Disputed Bolt"}
        assert any(obj.source is spell for obj in game.stack.objects())
        assert any(obj.source is not spell for obj in game.stack.objects())

        game.stack.pop().on_resolve(game)
        game.stack.pop().on_resolve(game)

        assert first_target.damage_marked == 1
        assert second_target.damage_marked == 1

    def test_your_sorcery_also_gets_casualty_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        casualty_fodder = Creature(name="Student", base_power=2, base_toughness=1)
        spell = DebateNotes(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, casualty_fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        _set_main_phase(game, 0)

        assert spell.get_casualty_value(game, p1) == 1

        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda cards, _description: casualty_fodder

        cast_without_resolution(game, p1, spell)

        assert game.get_graveyard(p1).contains(casualty_fodder)
        assert len(game.stack.objects()) == 2

        game.stack.pop().on_resolve(game)
        game.stack.pop().on_resolve(game)

        assert p1.sos_226_resolution_count == 2

    def test_declining_casualty_casts_only_the_original_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        casualty_fodder = Creature(name="Student", base_power=1, base_toughness=1)
        spell = DebateNotes(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, casualty_fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        _set_main_phase(game, 0)

        assert spell.get_casualty_value(game, p1) == 1

        p1.choose_yes_no = lambda _prompt: False

        cast_without_resolution(game, p1, spell)

        assert game.get_battlefield(p1).contains(casualty_fodder)
        assert not game.get_graveyard(p1).contains(casualty_fodder)
        assert len(game.stack.objects()) == 1

    def test_casualty_cannot_use_a_creature_with_less_than_one_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        powerless_creature = Creature(name="Meek Student", base_power=0, base_toughness=3)
        spell = DebateNotes(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, powerless_creature],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        _set_main_phase(game, 0)

        assert spell.get_casualty_value(game, p1) == 1

        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda cards, _description: powerless_creature

        cast_without_resolution(game, p1, spell)

        assert game.get_battlefield(p1).contains(powerless_creature)
        assert not game.get_graveyard(p1).contains(powerless_creature)
        assert len(game.stack.objects()) == 1

    def test_your_creature_spells_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        casualty_fodder = Creature(name="Student", base_power=1, base_toughness=1)
        creature_spell = Creature(
            name="Ordinary Creature",
            mana_cost=ManaCost.parse("{W}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[silverquill, casualty_fodder],
            hand=[creature_spell],
            mana={ManaType.WHITE: 1},
        )
        _set_main_phase(game, 0)

        assert creature_spell.get_casualty_value(game, p1) is None

        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda cards, _description: casualty_fodder

        cast_without_resolution(game, p1, creature_spell)

        assert game.get_battlefield(p1).contains(casualty_fodder)
        assert not game.get_graveyard(p1).contains(casualty_fodder)
        assert len(game.stack.objects()) == 1

    def test_opponents_spells_do_not_gain_casualty_from_your_silverquill(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        casualty_fodder = Creature(name="Opponent Student", base_power=1, base_toughness=1)
        spell = DebateNotes(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[silverquill])
        set_board_state(
            game,
            1,
            battlefield=[casualty_fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        _set_main_phase(game, 1)

        assert spell.get_casualty_value(game, p2) is None

        p2.choose_yes_no = lambda _prompt: True
        p2.choose_card = lambda cards, _description: casualty_fodder

        cast_without_resolution(game, p2, spell)

        assert game.get_battlefield(p2).contains(casualty_fodder)
        assert not game.get_graveyard(p2).contains(casualty_fodder)
        assert len(game.stack.objects()) == 1
