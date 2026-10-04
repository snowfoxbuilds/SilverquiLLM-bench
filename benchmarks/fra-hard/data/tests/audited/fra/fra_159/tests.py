import pytest
from card_impl import UldarosTheorix
from engine.card import Artifact, ArtifactCreature, Creature, Enchantment, Instant
from engine.decisions import Decision
from engine.game import exile
from engine.types import CardType, ManaCost, ManaType, Zone
from engine.zones import move_to_zone
from test_utils import (
    behavioral_game,
    cast_card,
    enter_permanent,
    prefer,
    resolve_stack,
)


def arrange():
    game = behavioral_game()
    player = game.players[0]
    player.mana_pool.add(ManaType.BLUE, 1)
    player.mana_pool.add(ManaType.BLACK, 2)
    player.mana_pool.add(ManaType.COLORLESS, 3)
    prefer(player, Decision.obj())
    return game, player


def grave(game, player, cls=Creature, name="Remembered", value=2):
    kwargs = {"name": name, "mana_cost": ManaCost(generic=value), "owner": player}
    if issubclass(cls, Creature):
        kwargs.update(base_power=2, base_toughness=3)
    card = cls(**kwargs)
    player.zones[Zone.GRAVEYARD].add(card)
    return card


def test_noncast_entry_does_not_exile_cards():
    game, player = arrange()
    target = grave(game, player)
    enter_permanent(game, player, UldarosTheorix())
    resolve_stack(game)
    assert player.zones[Zone.GRAVEYARD].contains(target)


@pytest.mark.parametrize("cls", [Creature, Artifact, Enchantment])
def test_cast_entry_exiles_original_and_casts_token_copy(cls):
    game, player = arrange()
    original = grave(game, player, cls)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.EXILE].contains(original)
    copies = [c for c in game.get_battlefield(player).get_all() if c.name == "Remembered"]
    assert len(copies) == 1 and copies[0] is not original and copies[0].is_token
    assert player.mana_pool.total() == 0


def test_mana_budget_is_shared_among_types():
    game, player = arrange()
    creature = grave(game, player, Creature, "Creature memory", 4)
    artifact = grave(game, player, Artifact, "Artifact memory", 4)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.EXILE].contains(creature) and player.zones[Zone.EXILE].contains(artifact)
    copies = [c for c in game.get_battlefield(player).get_all() if c.name.endswith("memory")]
    assert len(copies) == 1


def test_exact_six_budget_allows_multiple_spells():
    game, player = arrange()
    grave(game, player, Creature, "Creature memory", 3)
    grave(game, player, Artifact, "Artifact memory", 3)
    cast_card(game, player, UldarosTheorix())
    assert len([c for c in game.get_battlefield(player).get_all() if c.name.endswith("memory")]) == 2


def test_over_budget_card_is_exiled_but_not_cast():
    game, player = arrange()
    original = grave(game, player, Creature, value=7)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.EXILE].get_all() == [original]
    assert len(game.get_battlefield(player).get_all()) == 1


def test_only_one_card_per_type_is_selected():
    game, player = arrange()
    originals = [grave(game, player, Creature, f"Memory {i}", 1) for i in range(3)]
    cast_card(game, player, UldarosTheorix())
    assert sum(player.zones[Zone.EXILE].contains(c) for c in originals) == 1
    assert len(player.zones[Zone.GRAVEYARD].get_all()) == 2


def test_land_creature_is_not_eligible():
    game, player = arrange()
    target = grave(game, player)
    target.card_types.add(CardType.LAND)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.GRAVEYARD].contains(target)


def test_opponents_graveyard_is_not_eligible():
    game, player = arrange()
    opponent = game.players[1]
    target = grave(game, opponent)
    cast_card(game, player, UldarosTheorix())
    assert opponent.zones[Zone.GRAVEYARD].contains(target)


def test_targets_can_be_declined():
    game, player = arrange()
    target = grave(game, player)
    prefer(player)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.GRAVEYARD].contains(target)


def test_target_removed_in_response_is_not_copied():
    from engine.casting import resolve_top

    game, player = arrange()
    target = grave(game, player)
    cast_card(game, player, UldarosTheorix(), resolve=False)
    resolve_top(game)
    move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)
    resolve_stack(game)
    assert player.zones[Zone.HAND].contains(target)
    assert len(game.get_battlefield(player).get_all()) == 1


def test_leaving_uldaros_does_not_stop_pending_trigger():
    from engine.casting import resolve_top

    game, player = arrange()
    target = grave(game, player)
    uldaros = UldarosTheorix()
    cast_card(game, player, uldaros, resolve=False)
    resolve_top(game)
    exile(game, uldaros)
    resolve_stack(game)
    assert player.zones[Zone.EXILE].contains(target)
    assert any(c.name == target.name for c in game.get_battlefield(player).get_all())


def test_blink_does_not_repeat_cast_qualified_trigger():
    game, player = arrange()
    uldaros = UldarosTheorix()
    cast_card(game, player, uldaros)
    target = grave(game, player)
    move_to_zone(game, uldaros, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, uldaros, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert player.zones[Zone.GRAVEYARD].contains(target)


def test_multitype_cards_can_fill_different_type_slots():
    game, player = arrange()
    grave(game, player, ArtifactCreature, "First memory", 2)
    grave(game, player, ArtifactCreature, "Second memory", 2)
    cast_card(game, player, UldarosTheorix())
    assert len([c for c in game.get_battlefield(player).get_all() if c.name.endswith("memory")]) == 2


class MemoryDraw(Instant):
    def __init__(self, **kwargs):
        super().__init__(name="Memory draw", mana_cost=ManaCost(generic=2), **kwargs)

    def on_resolve(self, game):
        from engine.game import draw_card
        draw_card(game, self.controller)


def test_instant_copy_resolves_and_ceases_to_exist():
    game, player = arrange()
    original = MemoryDraw(owner=player)
    player.zones[Zone.GRAVEYARD].add(original)
    cast_card(game, player, UldarosTheorix())
    assert len(game.get_hand(player).get_all()) == 1
    assert player.zones[Zone.EXILE].get_all() == [original]
    assert not player.zones[Zone.GRAVEYARD].get_all()


def test_copy_tokens_do_not_inherit_counters():
    from engine.game import add_counter

    game, player = arrange()
    original = grave(game, player)
    add_counter(game, original, "+1/+1", 3)
    cast_card(game, player, UldarosTheorix())
    copied = next(card for card in game.get_battlefield(player).get_all() if card.name == original.name)
    assert copied.power == 2 and copied.toughness == 3 and not copied.counters


def test_copy_token_leaving_battlefield_ceases_without_moving_original():
    game, player = arrange()
    original = grave(game, player)
    cast_card(game, player, UldarosTheorix())
    copied = next(card for card in game.get_battlefield(player).get_all() if card.name == original.name)
    move_to_zone(game, copied, Zone.BATTLEFIELD, Zone.HAND)
    resolve_stack(game)
    assert player.zones[Zone.EXILE].contains(original)
    assert all(not player.zones[zone].contains(copied) for zone in Zone)


def test_one_invalid_target_does_not_stop_other_copy():
    from engine.casting import resolve_top

    game, player = arrange()
    original = grave(game, player)
    artifact = grave(game, player, Artifact, "Relic", 2)
    cast_card(game, player, UldarosTheorix(), resolve=False)
    resolve_top(game)
    move_to_zone(game, original, Zone.GRAVEYARD, Zone.HAND)
    resolve_stack(game)
    assert player.zones[Zone.HAND].contains(original)
    assert player.zones[Zone.EXILE].contains(artifact)
    assert any(card.name == "Relic" for card in game.get_battlefield(player).get_all())


def test_blinked_graveyard_target_is_not_same_target():
    from engine.casting import resolve_top

    game, player = arrange()
    target = grave(game, player)
    cast_card(game, player, UldarosTheorix(), resolve=False)
    resolve_top(game)
    move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)
    move_to_zone(game, target, Zone.HAND, Zone.GRAVEYARD)
    resolve_stack(game)
    assert player.zones[Zone.GRAVEYARD].contains(target)
    assert len(game.get_battlefield(player).get_all()) == 1


def test_zero_mana_value_copy_does_not_consume_budget():
    game, player = arrange()
    grave(game, player, Artifact, "Free memory", 0)
    grave(game, player, Creature, "Six memory", 6)
    cast_card(game, player, UldarosTheorix())
    assert len([c for c in game.get_battlefield(player).get_all() if c.name.endswith("memory")]) == 2


def test_single_multitype_card_is_copied_only_once():
    game, player = arrange()
    original = grave(game, player, ArtifactCreature)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.EXILE].get_all() == [original]
    assert len([c for c in game.get_battlefield(player).get_all() if c.name == original.name]) == 1


def test_uncast_over_budget_copy_cannot_be_saved_for_later():
    from engine.casting import CastingError, cast_spell

    game, player = arrange()
    original = grave(game, player, value=7)
    cast_card(game, player, UldarosTheorix())
    player.mana_pool.add(ManaType.COLORLESS, 7)
    with pytest.raises(CastingError):
        cast_spell(game, player, original)
    assert player.zones[Zone.EXILE].get_all() == [original]


def test_mandatory_target_missing_does_not_cast_copy_or_erase_original():
    from engine.types import TargetRequirement

    class MissingTarget(Instant):
        def __init__(self, **kwargs):
            super().__init__(name="Missing target", mana_cost=ManaCost(generic=1), **kwargs)

        def get_targets(self, game):
            return [TargetRequirement(
                lambda card: CardType.ARTIFACT in getattr(card, "card_types", set()),
                "Target artifact", Zone.BATTLEFIELD,
            )]

    game, player = arrange()
    original = MissingTarget(owner=player)
    player.zones[Zone.GRAVEYARD].add(original)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.EXILE].get_all() == [original]
    assert not player.zones[Zone.GRAVEYARD].get_all()
    assert not len(game.stack)


def test_free_copy_still_obeys_card_cast_restrictions():
    class Forbidden(Creature):
        def __init__(self, **kwargs):
            super().__init__(name="Forbidden", mana_cost=ManaCost(generic=1),
                             base_power=1, base_toughness=1, **kwargs)

        def can_cast(self, game):
            return False

    game, player = arrange()
    original = Forbidden(owner=player)
    player.zones[Zone.GRAVEYARD].add(original)
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.EXILE].get_all() == [original]
    assert len(game.get_battlefield(player).get_all()) == 1


def test_copy_is_cast_and_runs_its_cast_ability():
    from engine.game import gain_life

    class CastMemory(Creature):
        def __init__(self, **kwargs):
            super().__init__(name="Cast memory", mana_cost=ManaCost(generic=2),
                             base_power=2, base_toughness=2, **kwargs)

        def on_cast(self, game):
            gain_life(game, self.controller, 4)

    game, player = arrange()
    original = CastMemory(owner=player)
    player.zones[Zone.GRAVEYARD].add(original)
    cast_card(game, player, UldarosTheorix())
    assert player.life == 24
    assert player.zones[Zone.EXILE].contains(original)
    assert any(c.name == original.name and c.is_token for c in game.get_battlefield(player).get_all())


def test_free_x_spell_uses_zero_even_when_mana_is_available():
    from engine.game import gain_life

    class XMemory(Instant):
        def __init__(self, **kwargs):
            super().__init__(name="X memory", mana_cost=ManaCost.parse("{X}"), **kwargs)

        def on_resolve(self, game):
            gain_life(game, self.controller, self.x_value + 1)

    game, player = arrange()
    player.mana_pool.add(ManaType.COLORLESS, 4)
    original = XMemory(owner=player)
    player.zones[Zone.GRAVEYARD].add(original)
    prefer(player, Decision.obj(), Decision.number(4))
    cast_card(game, player, UldarosTheorix())
    assert player.life == 21 and player.mana_pool.total() == 4
    assert player.zones[Zone.EXILE].get_all() == [original]


def test_exile_selected_original_but_decline_casting_its_copy():
    from test_utils import object_preference

    game, player = arrange()
    original = grave(game, player)
    prefer(player, object_preference(game, original))
    cast_card(game, player, UldarosTheorix())
    assert player.zones[Zone.EXILE].get_all() == [original]
    assert len(game.get_battlefield(player).get_all()) == 1


def test_planeswalker_copy_starts_with_printed_loyalty_and_can_activate():
    from engine.card import LoyaltyAbility, Planeswalker
    from engine.game import gain_life
    from test_utils import activate_loyalty_ability

    class MemoryWalker(Planeswalker):
        def __init__(self, **kwargs):
            super().__init__(name="Memory walker", mana_cost=ManaCost(generic=3),
                             starting_loyalty=4, **kwargs)

        def get_loyalty_abilities(self):
            return [LoyaltyAbility(1, lambda g: gain_life(g, self.controller, 2))]

    game, player = arrange()
    original = MemoryWalker(owner=player)
    original.loyalty = 1
    player.zones[Zone.GRAVEYARD].add(original)
    cast_card(game, player, UldarosTheorix())
    copied = next(c for c in game.get_battlefield(player).get_all()
                  if c.name == original.name)
    assert copied is not original and copied.is_token and copied.loyalty == 4
    activate_loyalty_ability(game, player, copied)
    assert copied.loyalty == 5 and player.life == 20
    resolve_stack(game)
    assert player.life == 22 and player.zones[Zone.EXILE].contains(original)


def test_copy_registers_trigger_and_replacement_bound_to_copy():
    from engine.events import AddCounterReplacementEvent, GainsLifeTriggeredEvent
    from engine.game import add_counter, gain_life
    from engine.replacement_effects import ReplacementEffect
    from engine.triggers import TriggerRegistration

    class GrowingMemory(Creature):
        def __init__(self, **kwargs):
            super().__init__(name="Growing memory", mana_cost=ManaCost(generic=2),
                             base_power=2, base_toughness=2, **kwargs)

        def register_triggers(self, game):
            game.trigger_manager.register(TriggerRegistration(
                GainsLifeTriggeredEvent,
                lambda g, event: event.player is self.controller,
                lambda g: add_counter(g, self, "+1/+1", 1),
                self, self.controller,
            ))

        def register_replacement_effects(self, game):
            def double(g, event):
                event.amount *= 2
                return event

            game.replacement_manager.register(ReplacementEffect(
                AddCounterReplacementEvent, self,
                lambda g, event: event.permanent is self and event.counter_type == "+1/+1",
                double, self.controller,
            ))

    game, player = arrange()
    original = GrowingMemory(owner=player)
    player.zones[Zone.GRAVEYARD].add(original)
    cast_card(game, player, UldarosTheorix())
    copied = next(c for c in game.get_battlefield(player).get_all()
                  if c.name == original.name)
    gain_life(game, player, 1)
    resolve_stack(game)
    assert copied.counters.get("+1/+1") == 2 and copied.power == 4
    assert not original.counters and player.zones[Zone.EXILE].contains(original)
