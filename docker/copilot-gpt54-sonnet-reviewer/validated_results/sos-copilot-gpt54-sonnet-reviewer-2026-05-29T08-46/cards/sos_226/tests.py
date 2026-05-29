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


class CountermarkInstant(Instant):
    """Simple targeted instant used to verify granted casualty copies."""

    def __init__(self) -> None:
        super().__init__(
            name="Countermark Instant",
            mana_cost=ManaCost.parse("{W}"),
        )

    def get_targets(self, game) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if not getattr(self, "chosen_targets", []):
            return
        target = self.chosen_targets[0]
        target.plus_one_counters += 1


class DebateSummary(Sorcery):
    """Simple sorcery used to verify casualty on non-targeted sorceries."""

    def __init__(self) -> None:
        super().__init__(
            name="Debate Summary",
            mana_cost=ManaCost.parse("{1}{B}"),
        )

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 2


def _resolve_entire_stack(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestSilverquillTheDisputantProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_legendary_elder_dragon_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_and_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying_and_vigilance(self) -> None:
        keywords = SilverquillTheDisputant(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.VIGILANCE in keywords


class TestSilverquillTheDisputantCasualty:
    """Silverquill grants casualty 1 to your instant and sorcery spells."""

    def test_instant_spell_can_be_copied_by_sacrificing_a_power_one_creature_and_copy_can_retarget(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling Assistant",
            base_power=1,
            base_toughness=1,
        )
        first_target = Creature(
            name="First Debater",
            base_power=2,
            base_toughness=2,
        )
        second_target = Creature(
            name="Second Debater",
            base_power=2,
            base_toughness=2,
        )
        spell = CountermarkInstant()

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder, first_target, second_target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )

        target_choices = iter([first_target, second_target])
        p1.choose_target = lambda options, requirement: next(target_choices)
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)

        _resolve_entire_stack(game)

        assert first_target.plus_one_counters == 1
        assert second_target.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_sorcery_spell_can_be_copied_by_sacrificing_a_power_one_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Argument Token",
            base_power=1,
            base_toughness=1,
        )
        spell = DebateSummary()

        set_board_state(
            game,
            0,
            battlefield=[silverquill, fodder],
            hand=[spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: fodder
        life_before = p1.life

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2
        assert game.get_graveyard(p1).contains(fodder)

        _resolve_entire_stack(game)

        assert p1.life == life_before + 4
        assert game.get_graveyard(p1).contains(spell)

    def test_only_creatures_with_power_one_or_greater_are_offered_for_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        legal_fodder = Creature(
            name="Qualified Witness",
            base_power=1,
            base_toughness=1,
        )
        zero_power_creature = Creature(
            name="Silent Note-Taker",
            base_power=0,
            base_toughness=3,
        )
        spell = DebateSummary()

        set_board_state(
            game,
            0,
            battlefield=[silverquill, legal_fodder, zero_power_creature],
            hand=[spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        game.phase = Phase.PRECOMBAT_MAIN
        game.active_player_index = 0
        game.priority_player_index = 0

        p1.choose_yes_no = lambda prompt: True

        def _choose_casualty_creature(cards, description):
            assert legal_fodder in cards
            assert zero_power_creature not in cards
            return legal_fodder

        p1.choose_card = _choose_casualty_creature

        engine_cast_spell(game, p1, spell)

        assert len(game.stack) == 2
        assert game.get_graveyard(p1).contains(legal_fodder)
        assert game.get_battlefield(p1).contains(zero_power_creature)

    def test_declining_casualty_leaves_the_spell_uncopied_while_accepting_it_creates_a_copy(self) -> None:
        accepted_game = create_game()
        accepted_player = accepted_game.players[0]
        accepted_silverquill = SilverquillTheDisputant(
            owner=accepted_player,
            controller=accepted_player,
        )
        accepted_fodder = Creature(
            name="Accepted Assistant",
            base_power=2,
            base_toughness=2,
        )
        accepted_spell = DebateSummary()

        set_board_state(
            accepted_game,
            0,
            battlefield=[accepted_silverquill, accepted_fodder],
            hand=[accepted_spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        accepted_game.phase = Phase.PRECOMBAT_MAIN
        accepted_game.active_player_index = 0
        accepted_game.priority_player_index = 0
        accepted_player.choose_yes_no = lambda prompt: True
        accepted_player.choose_card = lambda cards, description: accepted_fodder

        engine_cast_spell(accepted_game, accepted_player, accepted_spell)

        declined_game = create_game()
        declined_player = declined_game.players[0]
        declined_silverquill = SilverquillTheDisputant(
            owner=declined_player,
            controller=declined_player,
        )
        declined_fodder = Creature(
            name="Declined Assistant",
            base_power=2,
            base_toughness=2,
        )
        declined_spell = DebateSummary()

        set_board_state(
            declined_game,
            0,
            battlefield=[declined_silverquill, declined_fodder],
            hand=[declined_spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        declined_game.phase = Phase.PRECOMBAT_MAIN
        declined_game.active_player_index = 0
        declined_game.priority_player_index = 0
        declined_player.choose_yes_no = lambda prompt: False

        engine_cast_spell(declined_game, declined_player, declined_spell)

        assert len(accepted_game.stack) == 2
        assert len(declined_game.stack) == 1
        assert accepted_game.get_graveyard(accepted_player).contains(accepted_fodder)
        assert declined_game.get_battlefield(declined_player).contains(declined_fodder)

    def test_only_instants_and_sorceries_get_casualty_not_creature_spells(self) -> None:
        instant_game = create_game()
        instant_player = instant_game.players[0]
        instant_silverquill = SilverquillTheDisputant(
            owner=instant_player,
            controller=instant_player,
        )
        instant_fodder = Creature(
            name="Instant Assistant",
            base_power=2,
            base_toughness=2,
        )
        instant_target = Creature(
            name="Instant Target",
            base_power=2,
            base_toughness=2,
        )
        instant_spell = CountermarkInstant()

        set_board_state(
            instant_game,
            0,
            battlefield=[instant_silverquill, instant_fodder, instant_target],
            hand=[instant_spell],
            mana={ManaType.WHITE: 1},
        )
        instant_player.choose_target = lambda options, requirement: instant_target
        instant_player.choose_yes_no = lambda prompt: True
        instant_player.choose_card = lambda cards, description: instant_fodder

        engine_cast_spell(instant_game, instant_player, instant_spell)

        creature_game = create_game()
        creature_player = creature_game.players[0]
        creature_silverquill = SilverquillTheDisputant(
            owner=creature_player,
            controller=creature_player,
        )
        creature_fodder = Creature(
            name="Creature Assistant",
            base_power=2,
            base_toughness=2,
        )
        creature_spell = Creature(
            name="Campus Guardian",
            mana_cost=ManaCost.parse("{1}{W}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(
            creature_game,
            0,
            battlefield=[creature_silverquill, creature_fodder],
            hand=[creature_spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        creature_game.phase = Phase.PRECOMBAT_MAIN
        creature_game.active_player_index = 0
        creature_game.priority_player_index = 0

        def _unexpected_yes_no(prompt: str) -> bool:
            raise AssertionError("Casualty should not be offered for creature spells")

        creature_player.choose_yes_no = _unexpected_yes_no

        engine_cast_spell(creature_game, creature_player, creature_spell)

        assert len(instant_game.stack) == 2
        assert len(creature_game.stack) == 1
        assert creature_game.get_battlefield(creature_player).contains(creature_fodder)

    def test_silverquill_grants_casualty_only_to_its_controllers_spells(self) -> None:
        your_game = create_game()
        you = your_game.players[0]
        your_silverquill = SilverquillTheDisputant(owner=you, controller=you)
        your_fodder = Creature(
            name="Your Assistant",
            base_power=2,
            base_toughness=2,
        )
        your_spell = DebateSummary()

        set_board_state(
            your_game,
            0,
            battlefield=[your_silverquill, your_fodder],
            hand=[your_spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        your_game.phase = Phase.PRECOMBAT_MAIN
        your_game.active_player_index = 0
        your_game.priority_player_index = 0
        you.choose_yes_no = lambda prompt: True
        you.choose_card = lambda cards, description: your_fodder

        engine_cast_spell(your_game, you, your_spell)

        opponents_game = create_game()
        p1, p2 = opponents_game.players
        opposing_silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opponent_fodder = Creature(
            name="Opponent Assistant",
            base_power=2,
            base_toughness=2,
        )
        opponent_spell = DebateSummary()

        set_board_state(opponents_game, 0, battlefield=[opposing_silverquill])
        set_board_state(
            opponents_game,
            1,
            battlefield=[opponent_fodder],
            hand=[opponent_spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        opponents_game.phase = Phase.PRECOMBAT_MAIN
        opponents_game.step = None
        opponents_game.active_player_index = 1
        opponents_game.priority_player_index = 1

        def _unexpected_yes_no(prompt: str) -> bool:
            raise AssertionError("Casualty should not be offered for an opponent's spell")

        p2.choose_yes_no = _unexpected_yes_no

        engine_cast_spell(opponents_game, p2, opponent_spell)

        assert len(your_game.stack) == 2
        assert len(opponents_game.stack) == 1
        assert opponents_game.get_battlefield(p2).contains(opponent_fodder)

    def test_silverquill_grants_casualty_only_while_on_the_battlefield(self) -> None:
        battlefield_game = create_game()
        battlefield_player = battlefield_game.players[0]
        battlefield_silverquill = SilverquillTheDisputant(
            owner=battlefield_player,
            controller=battlefield_player,
        )
        battlefield_fodder = Creature(
            name="Battlefield Speaker",
            base_power=2,
            base_toughness=2,
        )
        battlefield_spell = DebateSummary()

        set_board_state(
            battlefield_game,
            0,
            battlefield=[battlefield_silverquill, battlefield_fodder],
            hand=[battlefield_spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        battlefield_game.phase = Phase.PRECOMBAT_MAIN
        battlefield_game.active_player_index = 0
        battlefield_game.priority_player_index = 0
        battlefield_player.choose_yes_no = lambda prompt: True
        battlefield_player.choose_card = lambda cards, description: battlefield_fodder

        engine_cast_spell(battlefield_game, battlefield_player, battlefield_spell)

        hand_game = create_game()
        hand_player = hand_game.players[0]
        hand_silverquill = SilverquillTheDisputant(owner=hand_player, controller=hand_player)
        hand_fodder = Creature(
            name="Waiting Speaker",
            base_power=2,
            base_toughness=2,
        )
        hand_spell = DebateSummary()

        set_board_state(
            hand_game,
            0,
            battlefield=[hand_fodder],
            hand=[hand_silverquill, hand_spell],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1},
        )
        hand_game.phase = Phase.PRECOMBAT_MAIN
        hand_game.active_player_index = 0
        hand_game.priority_player_index = 0

        def _unexpected_yes_no(prompt: str) -> bool:
            raise AssertionError("Casualty should not be granted from outside the battlefield")

        hand_player.choose_yes_no = _unexpected_yes_no

        engine_cast_spell(hand_game, hand_player, hand_spell)

        assert len(battlefield_game.stack) == 2
        assert len(hand_game.stack) == 1
        assert hand_game.get_hand(hand_player).contains(hand_silverquill)
