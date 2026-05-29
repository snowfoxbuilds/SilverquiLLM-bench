"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.casting import cast_spell as cast_spell_to_stack, resolve_top
from engine.types import (
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TargetedLesson(Instant):
    """Minimal targeted instant used to exercise Silverquill's casualty grant."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Targeted Lesson")
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
        chosen_targets = list(getattr(self, "chosen_targets", []))
        target = chosen_targets[0] if chosen_targets else None
        if isinstance(target, Creature):
            target.plus_one_counters += 1


def _set_precombat_main(game, active_player_index: int = 0) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _creature(name: str, power: int = 2, toughness: int = 2) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_legendary_elder_dragon_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_and_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying_and_vigilance(self) -> None:
        keywords = SilverquillTheDisputant(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.VIGILANCE in keywords


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 to your instant and sorcery spells."""

    def test_declining_casualty_leaves_spell_uncopied_and_fodder_unsacrificed(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Inkling", power=1, toughness=1)
        target = _creature("Training Dummy")
        spell = TargetedLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        _set_precombat_main(game)
        silverquill.register_triggers(game)

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]
        p1.choose = lambda _options, _description: False  # type: ignore[method-assign]
        p1.choose_card = lambda _cards, _description: (_ for _ in ()).throw(  # type: ignore[method-assign]
            AssertionError("should not ask for a sacrifice when casualty is declined")
        )
        p1.choose_target = lambda _options, _requirement: target  # type: ignore[method-assign]

        cast_spell_to_stack(game, p1, spell)
        resolve_top(game)

        assert len(game.stack.objects()) == 0
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        assert target.plus_one_counters == 1

    def test_sacrificing_power_one_creature_copies_spell_and_sacrifices_immediately(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Inkling", power=1, toughness=1)
        target = _creature("Practice Golem")
        spell = TargetedLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        _set_precombat_main(game)
        silverquill.register_triggers(game)

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose = lambda _options, _description: True  # type: ignore[method-assign]
        p1.choose_card = lambda _cards, _description: fodder  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: target  # type: ignore[method-assign]

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack.objects()) == 2
        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)
        assert sum(obj.source.name == "Targeted Lesson" for obj in game.stack.objects()) == 2

    def test_casualty_copy_may_choose_new_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Inkling", power=1, toughness=1)
        original_target = _creature("Original Target")
        new_target = _creature("New Target")
        spell = TargetedLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(game, 1, battlefield=[original_target, new_target])
        _set_precombat_main(game)
        silverquill.register_triggers(game)

        target_choices = iter([original_target, new_target])
        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose = lambda _options, _description: True  # type: ignore[method-assign]
        p1.choose_card = lambda _cards, _description: fodder  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: next(target_choices)  # type: ignore[method-assign]

        cast_spell_to_stack(game, p1, spell)
        resolve_top(game)
        resolve_top(game)

        assert original_target.plus_one_counters == 1
        assert new_target.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_zero_power_creatures_cannot_pay_casualty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        powerless = _creature("Powerless Assistant", power=0, toughness=3)
        target = _creature("Training Dummy")
        spell = TargetedLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, powerless],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(game, 1, battlefield=[target])
        _set_precombat_main(game)
        silverquill.register_triggers(game)

        def _unexpected_prompt(*_args, **_kwargs):
            raise AssertionError("casualty should not be offered without a creature of power 1 or greater")

        p1.choose_yes_no = _unexpected_prompt  # type: ignore[method-assign]
        p1.choose = _unexpected_prompt  # type: ignore[method-assign]
        p1.choose_card = _unexpected_prompt  # type: ignore[method-assign]
        p1.choose_target = lambda _options, _requirement: target  # type: ignore[method-assign]

        cast_spell_to_stack(game, p1, spell)

        assert len(game.stack.objects()) == 1
        assert game.get_battlefield(p1).contains(powerless)
        assert not game.get_graveyard(p1).contains(powerless)

    def test_creature_spells_you_cast_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = _creature("Inkling", power=1, toughness=1)
        creature_spell = Creature(
            name="Campus Guard",
            mana_cost=ManaCost.parse("{1}{W}"),
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[creature_spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        _set_precombat_main(game)
        silverquill.register_triggers(game)

        def _unexpected_prompt(*_args, **_kwargs):
            raise AssertionError("creature spells should not gain casualty from Silverquill")

        p1.choose_yes_no = _unexpected_prompt  # type: ignore[method-assign]
        p1.choose = _unexpected_prompt  # type: ignore[method-assign]
        p1.choose_card = _unexpected_prompt  # type: ignore[method-assign]

        cast_spell_to_stack(game, p1, creature_spell)

        assert len(game.stack.objects()) == 1
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)

    def test_opponents_instants_and_sorceries_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opposing_fodder = _creature("Opposing Inkling", power=1, toughness=1)
        spell = Instant(
            name="Foreign Lesson",
            mana_cost=ManaCost.parse("{W}"),
            owner=p2,
            controller=p2,
        )

        set_board_state(game, 0, battlefield=[silverquill])
        set_board_state(
            game,
            1,
            battlefield=[opposing_fodder],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        _set_precombat_main(game, active_player_index=1)
        silverquill.register_triggers(game)

        def _unexpected_prompt(*_args, **_kwargs):
            raise AssertionError("Silverquill should not give casualty to opponents' spells")

        p2.choose_yes_no = _unexpected_prompt  # type: ignore[method-assign]
        p2.choose = _unexpected_prompt  # type: ignore[method-assign]
        p2.choose_card = _unexpected_prompt  # type: ignore[method-assign]

        cast_spell_to_stack(game, p2, spell)

        assert len(game.stack.objects()) == 1
        assert game.get_battlefield(p2).contains(opposing_fodder)
        assert not game.get_graveyard(p2).contains(opposing_fodder)
