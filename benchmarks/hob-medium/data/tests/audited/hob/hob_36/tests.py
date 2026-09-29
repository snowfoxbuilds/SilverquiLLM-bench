import pytest
from engine.card import Creature, Instant
from engine.game import add_counter, exile
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    advance_game_to_phase,
    behavioral_game,
    enter_permanent,
    object_preference,
    payment_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def bear(game, player, name="Bear", power=2):
    return put_on_battlefield(game, player, Creature(name=name, base_power=power, base_toughness=4))


def fund(player, **amounts):
    for name, amount in amounts.items():
        player.mana_pool.add(ManaType[name], amount)


from card_impl import ElrondMoonReader
from engine.card import ActivatedAbility


class TestCreature(Creature):
    __test__ = False

    def get_activated_abilities(self):
        return [ActivatedAbility(cost=lambda g, c: True, effect=lambda g: None)]


def arrange():
    game = behavioral_game()
    p = game.players[0]
    elrond = enter_permanent(game, p, ElrondMoonReader())
    resolve_stack(game)
    return game, p, elrond


def test_creature_activation_draws_once_each_turn():
    game, p, _elrond = arrange()
    creature = put_on_battlefield(
        game, p, TestCreature(name="Invoker", base_power=2, base_toughness=2)
    )
    activate_card_ability(game, p, creature)
    resolve_stack(game)
    activate_card_ability(game, p, creature)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1
    advance_game_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
    resolve_stack(game)
    activate_card_ability(game, p, creature)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 2


def test_opponents_activation_does_not_draw():
    game, p, _ = arrange()
    opponent = game.players[1]
    creature = put_on_battlefield(
        game, opponent, TestCreature(name="Other invoker", base_power=2, base_toughness=2)
    )
    activate_card_ability(game, opponent, creature)
    resolve_stack(game)
    assert not game.get_hand(p).get_all()


def test_noncreature_activation_does_not_draw():
    game, p, _ = arrange()
    source = put_on_battlefield(
        game, p, TestCreature(name="Artifact invoker", base_power=2, base_toughness=2)
    )
    source.card_types = {CardType.ARTIFACT}
    source.summoning_sick = False
    activate_card_ability(game, p, source)
    resolve_stack(game)
    assert not game.get_hand(p).get_all()


@pytest.mark.parametrize("count", [0, 1, 2])
def test_blink_returns_targets_at_next_end_step(count):
    game, p, elrond = arrange()
    targets = [bear(game, p, f"Friend {i}") for i in range(count)]
    prefer(p, *(object_preference(game, c) for c in targets))
    fund(p, BLUE=2, COLORLESS=5)
    activate_card_ability(game, p, elrond)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1
    assert all(p.zones[Zone.EXILE].contains(c) for c in targets)
    assert game.get_battlefield(p).contains(elrond)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert all(game.get_battlefield(p).contains(c) for c in targets)


def test_exiled_card_moved_elsewhere_does_not_return():
    game, p, elrond = arrange()
    target = bear(game, p)
    prefer(p, object_preference(game, target))
    fund(p, BLUE=2, COLORLESS=5)
    activate_card_ability(game, p, elrond)
    resolve_stack(game)
    move_to_zone(game, target, Zone.EXILE, Zone.HAND)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert p.zones[Zone.HAND].contains(target)


def test_return_survives_elrond_leaving():
    game, p, elrond = arrange()
    target = bear(game, p)
    prefer(p, object_preference(game, target))
    fund(p, BLUE=2, COLORLESS=5)
    activate_card_ability(game, p, elrond)
    resolve_stack(game)
    exile(game, elrond)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert game.get_battlefield(p).contains(target)


class ManaCreature(Creature):
    def get_activated_abilities(self):
        from engine.abilities import tap_cost
        from engine.card import ManaAbility

        return [
            ManaAbility(
                cost=tap_cost,
                mana_produced=lambda g: self.controller.mana_pool.add(ManaType.BLUE, 1),
            )
        ]

    def get_mana_abilities(self):
        return self.get_activated_abilities()


def test_mana_ability_triggers_a_draw_without_using_stack_itself():
    game, p, _elrond = arrange()
    source = put_on_battlefield(
        game, p, ManaCreature(name="Mana creature", base_power=1, base_toughness=1)
    )
    source.summoning_sick = False
    activate_card_ability(game, p, source)
    assert p.mana_pool.total() == 1
    assert len(game.stack) == 1
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1


def test_mana_payment_trigger_is_above_the_completed_spell():
    from engine.casting import cast_spell as cast

    game, p, elrond = arrange()
    source = put_on_battlefield(
        game, p, ManaCreature(name="Mana creature", base_power=1, base_toughness=1)
    )
    source.summoning_sick = False
    spell = Instant(name="Payment probe", mana_cost=ManaCost(generic=1), owner=p)
    game.get_hand(p).add(spell)
    prefer(p, *payment_preference(game, source))
    cast(game, p, spell)
    assert p.mana_pool.total() == 0
    assert game.stack.peek().source is elrond
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1


def test_failed_activation_does_not_consume_once_per_turn_trigger():
    from engine.abilities import AbilityError

    game, p, elrond = arrange()
    with pytest.raises(AbilityError):
        activate_card_ability(game, p, elrond)
    source = put_on_battlefield(
        game, p, TestCreature(name="Invoker", base_power=1, base_toughness=1)
    )
    activate_card_ability(game, p, source)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1


def test_blink_returns_a_fresh_untapped_permanent_without_counters():
    game, p, elrond = arrange()
    target = bear(game, p)
    target.is_tapped = True
    target.summoning_sick = False
    add_counter(game, target, "+1/+1", 2)
    prefer(p, object_preference(game, target))
    fund(p, BLUE=2, COLORLESS=5)
    activate_card_ability(game, p, elrond)
    resolve_stack(game)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert target.power == 2 and not target.is_tapped and target.summoning_sick


def test_blinked_stolen_permanent_returns_to_its_owner():
    game, p, elrond = arrange()
    owner = game.players[1]
    target = bear(game, p)
    target.owner = owner
    prefer(p, object_preference(game, target))
    fund(p, BLUE=2, COLORLESS=5)
    activate_card_ability(game, p, elrond)
    resolve_stack(game)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert game.get_battlefield(owner).contains(target) and target.controller is owner


class CastWatcher(Creature):
    def register_triggers(self, game):
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        game.trigger_manager.register(
            TriggerRegistration(
                SpellCastTriggeredEvent, None, lambda g: None, self, self.controller
            )
        )


def test_payment_and_cast_triggers_are_ordered_apnap():
    from engine.casting import cast_spell as cast

    game, p, elrond = arrange()
    opponent = game.players[1]
    game.active_player_index = 1
    enter_permanent(game, opponent, CastWatcher(name="Watcher", base_power=1, base_toughness=1))
    source = put_on_battlefield(
        game, p, ManaCreature(name="Mana creature", base_power=1, base_toughness=1)
    )
    source.summoning_sick = False
    spell = Instant(name="Payment probe", mana_cost=ManaCost(generic=1), owner=p)
    game.get_hand(p).add(spell)
    prefer(p, *payment_preference(game, source))
    cast(game, p, spell)
    assert game.stack.peek().source is elrond
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1


class ProtectionSpell(Instant):
    def __init__(self, target, color, **kwargs):
        from engine.types import ManaCost

        super().__init__(name="Protection response", mana_cost=ManaCost(), **kwargs)
        self.target, self.color = target, color

    def on_resolve(self, game):
        from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer
        from engine.protection import ProtectionAbility

        def apply(state):
            self.target.protections = [ProtectionAbility(self.color)]

        game.effect_manager.add(
            ContinuousEffect(
                source=self, layer=Layer.ABILITY, apply=apply, duration=DURATION_END_OF_TURN
            )
        )


@pytest.mark.parametrize("count", [1, 2])
def test_protection_gained_in_response_invalidates_only_that_target(count):
    from engine.types import Color
    from test_utils import cast_card

    game, p, elrond = arrange()
    targets = [bear(game, p, f"Target {i}") for i in range(count)]
    prefer(p, *(object_preference(game, card) for card in targets))
    fund(p, BLUE=2, COLORLESS=5)
    activate_card_ability(game, p, elrond)
    cast_card(game, p, ProtectionSpell(targets[0], Color.BLUE, owner=p), resolve=False)
    resolve_stack(game)
    assert game.get_battlefield(p).contains(targets[0])
    assert all(p.zones[Zone.EXILE].contains(card) for card in targets[1:])
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert all(game.get_battlefield(p).contains(card) for card in targets)


class HandInvoker(Creature):
    def get_activated_abilities(self):
        return [
            ActivatedAbility(
                cost=lambda g, c: True,
                effect=lambda g: None,
                can_activate=lambda g, c, p: g.get_hand(p).contains(c),
                description="{0}: Do nothing. Activate only from your hand.",
            )
        ]


def test_creature_card_activation_in_hand_does_not_use_draw_trigger():
    # Rule 109.2: "a creature" means a permanent, not a creature card in hand.
    game, p, _ = arrange()
    hand_card = HandInvoker(name="Hand invoker", owner=p, base_power=1, base_toughness=1)
    game.get_hand(p).add(hand_card)
    creature = put_on_battlefield(
        game, p, TestCreature(name="Battlefield invoker", base_power=1, base_toughness=1)
    )
    activate_card_ability(game, p, hand_card)
    resolve_stack(game)
    assert game.get_hand(p).get_all() == [hand_card]
    activate_card_ability(game, p, creature)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 2


class CreatureWithLoyalty(Creature):
    def __init__(self, **kwargs):
        super().__init__(name="Loyal creature", base_power=2, base_toughness=2, **kwargs)
        self.card_types.add(CardType.PLANESWALKER)
        self.loyalty = 3

    def get_loyalty_abilities(self):
        from engine.card import LoyaltyAbility

        return [LoyaltyAbility(loyalty_cost=1, effect=lambda g: None)]


def test_creature_loyalty_activation_triggers_draw():
    # Rule 606.1: loyalty abilities are activated abilities too.
    from test_utils import activate_loyalty_ability

    game, p, _ = arrange()
    creature = put_on_battlefield(game, p, CreatureWithLoyalty())
    activate_loyalty_ability(game, p, creature)
    resolve_stack(game)
    assert len(game.get_hand(p).get_all()) == 1


class CounterPendingAbility(Instant):
    def __init__(self, target, **kwargs):
        super().__init__(name="Counter pending ability", mana_cost=ManaCost(), **kwargs)
        self.target = target

    def on_resolve(self, game):
        game.stack.remove_object(self.target)


def test_countered_delayed_return_does_not_retry_next_end_step():
    # Rule 603.7b: the next end step uses up the delayed trigger even if countered.
    from test_utils import cast_card

    game, p, elrond = arrange()
    target = bear(game, p)
    prefer(p, object_preference(game, target))
    fund(p, BLUE=2, COLORLESS=5)
    activate_card_ability(game, p, elrond)
    resolve_stack(game)
    assert p.zones[Zone.EXILE].contains(target)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    cast_card(game, p, CounterPendingAbility(game.stack.peek(), owner=p))
    advance_game_to_phase(game, Phase.PRECOMBAT_MAIN)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    assert p.zones[Zone.EXILE].contains(target)
    assert not game.get_battlefield(p).contains(target)
