"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell, resolve_top
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


def _get_first_target(card) -> Creature | None:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


class TrainingCreature(Creature):
    """Simple creature used for casualty fodder and spell targets."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Creature")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)


class TrainingLesson(Sorcery):
    """Simple targeted sorcery for casualty-copy tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
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
        target = _get_first_target(self)
        if target is not None:
            target.plus_one_counters += 1


class TrainingRebuttal(Instant):
    """Simple targeted instant for casualty-copy tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Rebuttal")
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
        target = _get_first_target(self)
        if target is not None:
            target.plus_one_counters += 1


class LessonDrake(Creature):
    """Simple non-instant, non-sorcery spell."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Lesson Drake")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.FLYING)
        super().__init__(**kwargs)


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name_and_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_is_legendary_elder_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_power_toughness_and_colors(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.base_power == 4
        assert card.base_toughness == 4
        assert card.colors == {Color.BLACK, Color.WHITE}

    def test_has_flying_and_vigilance(self) -> None:
        keywords = SilverquillTheDisputant(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.VIGILANCE in keywords


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 only to your instants and sorceries."""

    @staticmethod
    def _set_precombat_main(game, active_player_index: int = 0) -> None:
        game.active_player_index = active_player_index
        game.priority_player_index = active_player_index
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    def test_sacrificing_a_power_one_creature_copies_a_sorcery_and_allows_new_targets(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = TrainingCreature(name="Ink Fodder", owner=p1, controller=p1)
        first_target = TrainingCreature(name="First Target", owner=p1, controller=p1)
        second_target = TrainingCreature(name="Second Target", owner=p1, controller=p1)
        spell = TrainingLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder, first_target, second_target],
            hand=[spell],
            mana={ManaType.COLORLESS: 1},
        )
        silverquill.register_triggers(game)
        self._set_precombat_main(game)

        chosen_targets = iter([first_target, second_target])
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder
        p1.choose_target = lambda options, requirement: next(chosen_targets)

        cast_spell(game, p1, spell)

        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)
        assert len(game.stack) == 2
        stack_objects = game.stack.objects()
        assert stack_objects[0].source is not spell
        assert stack_objects[1].source is spell

        resolve_top(game)
        resolve_top(game)

        assert first_target.plus_one_counters == 1
        assert second_target.plus_one_counters == 1

    def test_declining_casualty_keeps_the_spell_uncopied_and_preserves_the_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = TrainingCreature(name="Saved Fodder", owner=p1, controller=p1)
        target = TrainingCreature(name="Single Target", owner=p1, controller=p1)
        spell = TrainingLesson(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder, target],
            hand=[spell],
            mana={ManaType.COLORLESS: 1},
        )
        silverquill.register_triggers(game)
        self._set_precombat_main(game)

        p1.choose_yes_no = lambda prompt: False
        p1.choose_target = lambda options, requirement: target

        cast_spell(game, p1, spell)

        assert len(game.stack) == 1
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)

        resolve_top(game)

        assert target.plus_one_counters == 1

    def test_casualty_choice_offers_only_creatures_with_power_one_or_greater(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        zero_power = TrainingCreature(
            name="Zero Power",
            owner=p1,
            controller=p1,
            base_power=0,
            base_toughness=2,
        )
        legal_fodder = TrainingCreature(name="Legal Fodder", owner=p1, controller=p1)
        target = TrainingCreature(name="Casualty Target", owner=p1, controller=p1)
        spell = TrainingLesson(owner=p1, controller=p1)
        seen: dict[str, list[Creature]] = {}

        set_board_state(
            game,
            0,
            battlefield=[silverquill, zero_power, legal_fodder, target],
            hand=[spell],
            mana={ManaType.COLORLESS: 1},
        )
        silverquill.register_triggers(game)
        self._set_precombat_main(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_target = lambda options, requirement: target

        def choose_card(cards, description):
            seen["cards"] = list(cards)
            return legal_fodder

        p1.choose_card = choose_card

        cast_spell(game, p1, spell)

        assert legal_fodder in seen["cards"]
        assert zero_power not in seen["cards"]
        assert game.get_graveyard(p1).contains(legal_fodder)
        assert game.get_battlefield(p1).contains(zero_power)

    def test_instants_you_cast_also_gain_casualty_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = TrainingCreature(name="Instant Fodder", owner=p1, controller=p1)
        first_target = TrainingCreature(name="Instant Target A", owner=p1, controller=p1)
        second_target = TrainingCreature(name="Instant Target B", owner=p1, controller=p1)
        spell = TrainingRebuttal(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder, first_target, second_target],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        silverquill.register_triggers(game)
        self._set_precombat_main(game)

        chosen_targets = iter([first_target, second_target])
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder
        p1.choose_target = lambda options, requirement: next(chosen_targets)

        cast_spell(game, p1, spell)
        resolve_top(game)
        resolve_top(game)

        assert first_target.plus_one_counters == 1
        assert second_target.plus_one_counters == 1

    def test_noninstant_and_nonsorcery_spells_are_not_granted_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = TrainingCreature(name="Creature Fodder", owner=p1, controller=p1)
        creature_spell = LessonDrake(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 2},
        )
        silverquill.register_triggers(game)
        self._set_precombat_main(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder

        cast_spell(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)

        resolve_top(game)

        assert game.get_battlefield(p1).contains(creature_spell)

    def test_only_your_own_instants_and_sorceries_gain_casualty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opponent_fodder = TrainingCreature(name="Opponent Fodder", owner=p2, controller=p2)
        opponent_target = TrainingCreature(name="Opponent Target", owner=p2, controller=p2)
        opponent_spell = TrainingLesson(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[silverquill])
        set_board_state(
            game,
            1,
            battlefield=[opponent_fodder, opponent_target],
            hand=[opponent_spell],
            mana={ManaType.COLORLESS: 1},
        )
        silverquill.register_triggers(game)
        self._set_precombat_main(game, active_player_index=1)

        p2.choose_yes_no = lambda prompt: True
        p2.choose_card = lambda cards, description: opponent_fodder
        p2.choose_target = lambda options, requirement: opponent_target

        cast_spell(game, p2, opponent_spell)

        assert len(game.stack) == 1
        assert game.get_battlefield(p2).contains(opponent_fodder)
        assert not game.get_graveyard(p2).contains(opponent_fodder)

        resolve_top(game)

        assert opponent_target.plus_one_counters == 1
