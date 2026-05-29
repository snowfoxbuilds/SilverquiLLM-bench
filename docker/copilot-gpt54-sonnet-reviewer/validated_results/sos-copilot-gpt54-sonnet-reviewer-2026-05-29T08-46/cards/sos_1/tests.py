"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import counter_spell, get_cost_reduction
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import cast_spell, create_game, set_board_state


class GraveyardBolt(Instant):
    """Simple graveyard-cast instant used to validate the attack trigger."""

    def __init__(self) -> None:
        super().__init__(name="Graveyard Bolt", mana_cost=ManaCost.parse("{3}{R}"))
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        controller = self.controller
        if controller is None:
            return
        opponent = next(player for player in game.players if player is not controller)
        opponent.life -= 3


class GraveyardFlame( Sorcery):
    """Simple graveyard-cast sorcery used to validate the attack trigger."""

    def __init__(self) -> None:
        super().__init__(name="Graveyard Flame", mana_cost=ManaCost.parse("{4}{R}"))
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        controller = self.controller
        if controller is None:
            return
        opponent = next(player for player in game.players if player is not controller)
        opponent.life -= 2


def _resolve_entire_stack(game) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_legendary_avatar_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_power_and_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestTheDawningArchaicCostReduction:
    """The generic cost reduction should count only your instant/sorcery cards."""

    def test_counts_only_instants_and_sorceries_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = TheDawningArchaic(owner=p1, controller=p1)
        your_graveyard = [
            Instant(name="First Instant"),
            Sorcery(name="First Sorcery"),
            Instant(name="Second Instant"),
            Creature(name="Grizzly Bears", base_power=2, base_toughness=2),
        ]
        opponent_graveyard = [
            Instant(name="Opponent Instant"),
            Sorcery(name="Opponent Sorcery"),
        ]

        set_board_state(game, 0, graveyard=your_graveyard)
        set_board_state(game, 1, graveyard=opponent_graveyard)

        assert get_cost_reduction(game, card, p1) == 3

    def test_can_be_cast_for_zero_mana_with_ten_eligible_cards(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic(owner=game.players[0], controller=game.players[0])
        graveyard = [Instant(name=f"Spell {idx}") for idx in range(10)]

        set_board_state(game, 0, hand=[archaic], graveyard=graveyard, mana={})

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(game.players[0]).contains(archaic)
        assert game.players[0].mana_pool.total() == 0


class TestTheDawningArchaicAttackTrigger:
    """Attacking should let you free-cast an instant or sorcery from your graveyard."""

    def test_attack_trigger_casts_an_instant_from_your_graveyard_for_free(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardBolt()

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], mana={})
        archaic.register_triggers(game)
        p1.choose_card = lambda cards, description: spell
        p1.choose_target = lambda options, requirement: spell
        p1.choose_yes_no = lambda prompt: True

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_entire_stack(game)

        assert spell.was_resolved is True
        assert p2.life == 17
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
        assert p1.mana_pool.total() == 0

    def test_attack_trigger_casts_a_sorcery_from_your_graveyard_for_free(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardFlame()

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], mana={})
        archaic.register_triggers(game)
        p1.choose_card = lambda cards, description: spell
        p1.choose_target = lambda options, requirement: spell
        p1.choose_yes_no = lambda prompt: True

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_entire_stack(game)

        assert spell.was_resolved is True
        assert p2.life == 18
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_attack_trigger_does_not_retarget_if_original_target_leaves_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        locked_spell = GraveyardBolt()
        other_spell = GraveyardFlame()

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            graveyard=[locked_spell, other_spell],
            mana={},
        )
        archaic.register_triggers(game)
        p1.choose_target = lambda options, requirement: locked_spell
        p1.choose_yes_no = lambda prompt: True

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        move_to_zone(game, locked_spell, Zone.GRAVEYARD, Zone.HAND)
        _resolve_entire_stack(game)

        assert locked_spell.was_resolved is False
        assert other_spell.was_resolved is False
        assert game.get_hand(p1).contains(locked_spell)
        assert game.get_graveyard(p1).contains(other_spell)
        assert not game.get_exile(p1).contains(locked_spell)
        assert not game.get_exile(p1).contains(other_spell)
        assert p2.life == 20
        assert game.stack.is_empty()

    def test_countered_free_cast_spell_is_exiled_instead_of_returning_to_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardBolt()

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], mana={})
        archaic.register_triggers(game)
        p1.choose_target = lambda options, requirement: spell
        p1.choose_yes_no = lambda prompt: True

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        cast_obj = game.stack.peek()
        assert cast_obj is not None
        assert cast_obj.source is spell

        counter_spell(game, cast_obj)

        assert spell.was_resolved is False
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
        assert p2.life == 20
        assert game.stack.is_empty()

    def test_you_may_decline_to_cast_the_targeted_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardBolt()

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], mana={})
        archaic.register_triggers(game)
        p1.choose_card = lambda cards, description: spell
        p1.choose_target = lambda options, requirement: spell
        p1.choose_yes_no = lambda prompt: False

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_entire_stack(game)

        assert spell.was_resolved is False
        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_exile(p1).contains(spell)
        assert p2.life == 20

    def test_attack_trigger_is_a_noop_without_an_instant_or_sorcery_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[bear])
        archaic.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_entire_stack(game)

        assert game.get_graveyard(p1).contains(bear)
        assert not game.get_exile(p1).contains(bear)
        assert game.stack.is_empty()
