import pytest
from engine.card import Creature, Instant
from engine.game import add_counter, create_token
from engine.types import ManaCost, ManaType, Supertype, Zone
from test_utils import (
    activate_card_ability,
    behavioral_game,
    enter_permanent,
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


from card_impl import TheNotaryHobbits
from engine.abilities import AbilityError


def arrange():
    game = behavioral_game()
    p = game.players[0]
    card = enter_permanent(game, p, TheNotaryHobbits())
    resolve_stack(game)
    return game, p, card


def test_entry_creates_two_nonlegendary_halfling_copies():
    game, p, card = arrange()
    copies = [c for c in game.get_battlefield(p).get_all() if c is not card]
    assert len(copies) == 2
    for token in copies:
        assert token.is_token and token.name == card.name
        assert (token.power, token.toughness) == (1, 1)
        assert "Halfling" in token.subtypes
        assert Supertype.LEGENDARY not in token.supertypes
    assert Supertype.LEGENDARY in card.supertypes


def test_token_entry_does_not_create_more_tokens():
    game = behavioral_game()
    p = game.players[0]
    create_token(game, p, TheNotaryHobbits())
    resolve_stack(game)
    assert len(game.get_battlefield(p).get_all()) == 1


def test_mana_counts_all_your_halflings_only():
    game, p, card = arrange()
    opponent = game.players[1]
    other = bear(game, p, "Other Halfling")
    other.subtypes = {"Halfling"}
    enemy = bear(game, opponent, "Enemy Halfling")
    enemy.subtypes = {"Halfling"}
    card.summoning_sick = False
    activate_card_ability(game, p, card)
    assert p.mana_pool.total() == 4
    assert game.stack.is_empty()


def test_summoning_sick_mana_activation_is_illegal():
    game, p, card = arrange()
    with pytest.raises(AbilityError):
        activate_card_ability(game, p, card)
    assert p.mana_pool.total() == 0


def test_tapped_notary_cannot_activate_twice():
    game, p, card = arrange()
    card.summoning_sick = False
    activate_card_ability(game, p, card)
    with pytest.raises(AbilityError):
        activate_card_ability(game, p, card)
    assert p.mana_pool.total() == 3


def test_copies_have_independent_mana_abilities():
    game, p, _card = arrange()
    for token in game.get_battlefield(p).get_all():
        token.summoning_sick = False
        activate_card_ability(game, p, token)
    assert p.mana_pool.total() == 9


def test_copies_do_not_copy_counters():
    game = behavioral_game()
    p = game.players[0]
    card = enter_permanent(game, p, TheNotaryHobbits())
    add_counter(game, card, "+1/+1", 3)
    resolve_stack(game)
    copies = [c for c in game.get_battlefield(p).get_all() if c is not card]
    assert all((c.power, c.toughness) == (1, 1) for c in copies)


def test_mana_ability_can_pay_for_another_spell():
    from engine.casting import cast_spell as cast

    game, p, card = arrange()
    card.summoning_sick = False
    spell = Instant(name="Payment probe", mana_cost=ManaCost(generic=3), owner=p)
    game.get_hand(p).add(spell)
    prefer(p, *payment_preference(game, card))
    cast(game, p, spell)
    assert card.is_tapped and p.mana_pool.total() == 0
    assert len(game.stack) == 1 and game.stack.peek().source is spell
    resolve_stack(game)
    assert p.zones[Zone.GRAVEYARD].contains(spell)


def test_new_copies_are_summoning_sick_even_if_original_is_not():
    from engine.abilities import AbilityError

    game = behavioral_game()
    p = game.players[0]
    card = enter_permanent(game, p, TheNotaryHobbits())
    card.summoning_sick = False
    resolve_stack(game)
    for token in game.get_battlefield(p).get_all():
        if token is not card:
            with pytest.raises(AbilityError):
                activate_card_ability(game, p, token)


class GrantHaste(Instant):
    def __init__(self, target, **kwargs):
        super().__init__(name="Grant haste", mana_cost=ManaCost(), **kwargs)
        self.target = target

    def on_resolve(self, game):
        from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer
        from engine.types import Keyword

        def apply(state):
            self.target.keywords |= Keyword.HASTE

        game.effect_manager.add(
            ContinuousEffect(self, Layer.ABILITY, apply=apply, duration=DURATION_END_OF_TURN)
        )


def test_haste_allows_mana_activation_on_the_turn_notary_enters():
    # Rules 602.5a and 702.10c waive the tap-cost restriction for haste.
    from test_utils import cast_card

    game, p, card = arrange()
    cast_card(game, p, GrantHaste(card, owner=p))
    activate_card_ability(game, p, card)
    assert card.is_tapped
    assert p.mana_pool.get(ManaType.COLORLESS) == 3


class TakeControl(Instant):
    def __init__(self, target, **kwargs):
        super().__init__(name="Take control", mana_cost=ManaCost(), **kwargs)
        self.target = target

    def on_resolve(self, game):
        game.get_battlefield(self.target.controller).remove(self.target)
        self.target.controller = self.controller
        game.get_battlefield(self.controller).add(self.target)


def test_pending_copies_belong_to_the_original_trigger_controller():
    # Rule 603.3a fixes a trigger's controller when it triggers.
    from test_utils import cast_card

    game = behavioral_game()
    p, opponent = game.players
    card = enter_permanent(game, p, TheNotaryHobbits())
    cast_card(game, opponent, TakeControl(card, owner=opponent))
    assert game.get_battlefield(opponent).get_all() == [card]
    copies = game.get_battlefield(p).get_all()
    assert len(copies) == 2
    assert all(c.name == card.name and c.is_token for c in copies)
