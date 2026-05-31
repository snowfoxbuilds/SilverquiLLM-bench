"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.casting import cast_spell
from engine.card import Creature, Instant, Sorcery
from engine.game import deal_damage
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype, TargetRequirement, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


class _DebateBolt(Instant):
    """Simple targeted instant used to observe casualty copying."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Debate Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if not getattr(self, "chosen_targets", []):
            return
        deal_damage(game, self, self.chosen_targets[0], 2)


class _ClosingArgument(Sorcery):
    """Simple targeted sorcery used to verify sorceries gain casualty too."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Closing Argument")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def get_targets(self, game):
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game) -> None:
        if not getattr(self, "chosen_targets", []):
            return
        deal_damage(game, self, self.chosen_targets[0], 2)


def _put_onto_battlefield(game, player, permanent) -> None:
    player.zones[Zone.HAND].add(permanent)
    permanent.owner = player
    permanent.controller = player
    move_to_zone(game, permanent, Zone.HAND, Zone.BATTLEFIELD)


def _set_main_phase(game, active_player_index: int = 0) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestSilverquillTheDisputantProperties:
    """Static characteristics should match the card spec."""

    def test_is_a_legendary_four_four_elder_dragon_with_flying_and_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes
        assert card.base_power == 4
        assert card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords


class TestSilverquillTheDisputantCasualty:
    """Silverquill should grant casualty 1 to your instants and sorceries."""

    def test_your_instant_can_be_copied_by_sacrificing_a_creature_with_power_one_or_greater(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Campus Witness",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = _DebateBolt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[fodder],
            hand=[spell],
            mana={ManaType.COLORLESS: 1},
        )
        _put_onto_battlefield(game, p1, silverquill)
        _set_main_phase(game)

        chosen_player_targets = [p2, p1]

        def choose_target(options, requirement):
            if any(hasattr(option, "life") for option in options):
                chosen = chosen_player_targets.pop(0)
                assert chosen in options
                return chosen
            assert fodder in options
            return fodder

        p1.choose_yes_no = lambda prompt: True
        p1.choose_target = choose_target
        p1.choose_card = lambda cards, description: fodder

        cast_spell(game, p1, spell)

        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_battlefield(p1).contains(fodder)
        assert len(game.stack) == 2

        stack_objects = game.stack.objects()
        original_obj = next(obj for obj in stack_objects if obj.source is spell)
        copy_obj = next(obj for obj in stack_objects if obj.source is not spell)

        assert original_obj.chosen_targets == [p2]
        assert copy_obj.chosen_targets == [p1]

        _resolve_all(game)

        assert p1.life == 18
        assert p2.life == 18
        assert game.get_graveyard(p1).contains(spell)
        assert sum(
            1
            for card in game.get_graveyard(p1).get_all()
            if getattr(card, "name", None) == "Debate Bolt"
        ) == 1

    def test_your_sorcery_also_gains_casualty_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Inkling Intern",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = _ClosingArgument(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[fodder],
            hand=[spell],
            mana={ManaType.COLORLESS: 2},
        )
        _put_onto_battlefield(game, p1, silverquill)
        _set_main_phase(game)

        decisions = [True, False]

        def choose_yes_no(prompt: str) -> bool:
            assert decisions, f"unexpected yes/no prompt: {prompt}"
            return decisions.pop(0)

        def choose_target(options, requirement):
            if any(hasattr(option, "life") for option in options):
                assert p2 in options
                return p2
            assert fodder in options
            return fodder

        p1.choose_yes_no = choose_yes_no
        p1.choose_target = choose_target
        p1.choose_card = lambda cards, description: fodder

        cast_spell(game, p1, spell)

        assert len(game.stack) == 2
        _resolve_all(game)

        assert p2.life == 16
        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(spell)

    def test_no_copy_is_created_when_you_control_no_creature_with_power_one_or_greater(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        ineligible_creature = Creature(
            name="Exhausted Scribe",
            owner=p1,
            controller=p1,
            base_power=0,
            base_toughness=3,
        )
        spell = _DebateBolt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[ineligible_creature],
            hand=[spell],
            mana={ManaType.COLORLESS: 1},
        )
        _put_onto_battlefield(game, p1, silverquill)
        _set_main_phase(game)

        def choose_target(options, requirement):
            if any(hasattr(option, "life") for option in options):
                assert p2 in options
                return p2
            raise AssertionError("casualty should not ask for an ineligible sacrifice creature")

        p1.choose_yes_no = lambda prompt: True
        p1.choose_target = choose_target
        p1.choose_card = lambda cards, description: (_ for _ in ()).throw(
            AssertionError("casualty should not ask for a sacrifice choice without a legal creature")
        )

        cast_spell(game, p1, spell)

        assert len(game.stack) == 1
        _resolve_all(game)

        assert game.get_battlefield(p1).contains(ineligible_creature)
        assert not game.get_graveyard(p1).contains(ineligible_creature)
        assert p2.life == 18

    def test_opponents_instants_and_sorceries_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opponent_fodder = Creature(
            name="Borrowed Witness",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        opponent_spell = _DebateBolt(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[], hand=[])
        set_board_state(
            game,
            1,
            battlefield=[opponent_fodder],
            hand=[opponent_spell],
            mana={ManaType.COLORLESS: 1},
        )
        _put_onto_battlefield(game, p1, silverquill)
        _set_main_phase(game, active_player_index=1)

        def choose_target(options, requirement):
            if any(hasattr(option, "life") for option in options):
                assert p1 in options
                return p1
            raise AssertionError("opponent spell should not receive casualty target choices")

        p2.choose_yes_no = lambda prompt: (_ for _ in ()).throw(
            AssertionError("opponent spell should not be offered casualty")
        )
        p2.choose_target = choose_target
        p2.choose_card = lambda cards, description: (_ for _ in ()).throw(
            AssertionError("opponent spell should not choose a casualty sacrifice")
        )

        cast_spell(game, p2, opponent_spell)

        assert len(game.stack) == 1
        _resolve_all(game)

        assert game.get_battlefield(p2).contains(opponent_fodder)
        assert not game.get_graveyard(p2).contains(opponent_fodder)
        assert p1.life == 18

    def test_non_instant_and_non_sorcery_spells_you_cast_do_not_gain_casualty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Ink Trainee",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        creature_spell = Creature(
            name="Patient Pupil",
            mana_cost=ManaCost.parse("{1}"),
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[fodder],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 1},
        )
        _put_onto_battlefield(game, p1, silverquill)
        _set_main_phase(game)

        p1.choose_yes_no = lambda prompt: (_ for _ in ()).throw(
            AssertionError("creature spells should not be offered casualty")
        )

        cast_spell(game, p1, creature_spell)

        assert len(game.stack) == 1
        _resolve_all(game)

        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(fodder)
        assert game.get_battlefield(p1).contains(creature_spell)
