"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.combat import _can_block
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import cast_spell, create_game, set_board_state


class TestTheDawningArchaicProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_avatar_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_has_mana_cost_and_power_toughness_from_spec(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach_keyword(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_reach_allows_it_to_block_a_flying_attacker(self) -> None:
        archaic = TheDawningArchaic(owner=None)
        flier = Creature(
            name="Sky Drake",
            base_power=2,
            base_toughness=2,
            keywords=Keyword.FLYING,
        )
        assert _can_block(archaic, flier) is True


class TestTheDawningArchaicCostReduction:
    """The cost reduction depends on instant/sorcery cards in your graveyard."""

    def test_cost_reduction_counts_only_your_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = TheDawningArchaic(owner=p1, controller=p1)
        own_instant = Instant(name="Opt", mana_cost=ManaCost.parse("{U}"))
        own_sorcery = Sorcery(name="Ponder", mana_cost=ManaCost.parse("{U}"))
        own_creature = Creature(name="Bear", base_power=2, base_toughness=2)
        opposing_instant = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"))

        set_board_state(
            game,
            0,
            graveyard=[own_instant, own_sorcery, own_creature],
        )
        set_board_state(game, 1, graveyard=[opposing_instant])

        assert card.cost_reduction(game) == 2

    def test_can_be_cast_for_seven_mana_with_three_spells_in_your_graveyard(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic(owner=None)

        set_board_state(
            game,
            0,
            hand=[archaic],
            graveyard=[
                Instant(name="Opt", mana_cost=ManaCost.parse("{U}")),
                Sorcery(name="Ponder", mana_cost=ManaCost.parse("{U}")),
                Instant(name="Shock", mana_cost=ManaCost.parse("{R}")),
            ],
            mana={ManaType.COLORLESS: 7},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(game.players[0]).contains(archaic)


class TestTheDawningArchaicAttackTrigger:
    """Attack-trigger registration and resolution contract."""

    @staticmethod
    def _fire_attack(game, archaic: TheDawningArchaic) -> None:
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

    def test_registers_one_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)

        archaic.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_other_creature_attacking_does_not_trigger_it(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        other = Creature(name="Bear", base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[archaic, other])
        archaic.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other, attacker=other),
        )

        assert game.stack.is_empty()

    def test_its_attack_does_not_create_a_trigger_without_a_legal_target(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic(owner=None)

        set_board_state(game, 0, battlefield=[archaic])
        archaic.register_triggers(game)

        self._fire_attack(game, archaic)

        assert game.stack.is_empty()

    def test_attack_trigger_chooses_and_exposes_target_on_stack_object(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        spell = Instant(name="Sift", mana_cost=ManaCost.parse("{8}{U}"))

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        p1.choose_target = lambda _options, _requirement: spell

        archaic.register_triggers(game)
        self._fire_attack(game, archaic)

        trigger_obj = game.stack.peek()
        assert trigger_obj is not None
        assert trigger_obj.targets == [spell]
        assert len(trigger_obj.target_requirements) == 1
        assert trigger_obj.target_requirements[0].zone is Zone.GRAVEYARD

    def test_trigger_does_not_cast_if_target_left_graveyard_before_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        spell = Instant(name="Sift", mana_cost=ManaCost.parse("{8}{U}"))

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        p1.choose_yes_no = lambda _prompt: True
        p1.choose_target = lambda _options, _requirement: spell

        archaic.register_triggers(game)
        self._fire_attack(game, archaic)

        move_to_zone(game, spell, Zone.GRAVEYARD, Zone.HAND)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_hand(p1).contains(spell)
        assert not game.stack.objects()

    def test_trigger_is_not_created_when_only_opponents_graveyard_has_a_spell(self) -> None:
        game = create_game()
        p2 = game.players[1]
        archaic = TheDawningArchaic(owner=None)
        opposing_spell = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"))

        set_board_state(game, 0, battlefield=[archaic])
        set_board_state(game, 1, graveyard=[opposing_spell])

        archaic.register_triggers(game)
        self._fire_attack(game, archaic)

        assert game.stack.is_empty()
        assert game.get_graveyard(p2).contains(opposing_spell)

    def test_player_may_decline_casting_the_targeted_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        spell = Instant(name="Sift", mana_cost=ManaCost.parse("{8}{U}"))

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        p1.choose_yes_no = lambda _prompt: False
        p1.choose_card = lambda _cards, _description: spell
        p1.choose_target = lambda _options, _requirement: spell

        archaic.register_triggers(game)
        self._fire_attack(game, archaic)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell)

    def test_trigger_casts_a_chosen_graveyard_spell_without_paying_mana_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        spell = Instant(name="Sift", mana_cost=ManaCost.parse("{8}{U}"))

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda _cards, _description: spell
        p1.choose_target = lambda _options, _requirement: spell

        archaic.register_triggers(game)
        self._fire_attack(game, archaic)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert not game.get_graveyard(p1).contains(spell)
        assert not game.stack.is_empty()
        assert game.stack.peek().source is spell
        assert game.stack.peek().controller is p1

    def test_spell_cast_with_the_trigger_is_exiled_after_it_resolves(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        spell = Sorcery(name="Mind Draft", mana_cost=ManaCost.parse("{9}{U}"))

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])

        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda _cards, _description: spell
        p1.choose_target = lambda _options, _requirement: spell

        archaic.register_triggers(game)
        self._fire_attack(game, archaic)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)

        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
