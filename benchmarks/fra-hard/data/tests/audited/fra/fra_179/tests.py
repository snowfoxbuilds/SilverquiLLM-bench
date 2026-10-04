import pytest
from card_impl import HallofEchoes
from engine.abilities import AbilityError
from engine.card import ActivatedAbility, Creature, Instant
from engine.game import add_counter, exile
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import (
    activate_card_ability,
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    enter_permanent,
    object_preference,
    prefer,
    resolve_stack,
)


class EchoCreature(Creature):
    def __init__(self, **kwargs):
        super().__init__(name="Echo creature", mana_cost=ManaCost(generic=2),
                         base_power=3, base_toughness=4, keywords=Keyword.FLYING, **kwargs)

    def get_activated_abilities(self):
        return [ActivatedAbility(lambda g, s: True,
            lambda g: add_counter(g, self, "+1/+1", 1), "Grow")]


def arrange():
    game = behavioral_game()
    player = game.players[0]
    hall = enter_permanent(game, player, HallofEchoes())
    target = enter_permanent(game, player, EchoCreature())
    prefer(player, object_preference(game, target))
    player.mana_pool.add(ManaType.COLORLESS, 5)
    return game, player, hall, target


def test_mana_ability_adds_colorless_without_stack():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall, 1)
    assert hall.is_tapped and player.mana_pool.total() == 6 and not len(game.stack)


def test_copy_has_characteristics_and_abilities():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.name == target.name and hall.power == 3 and hall.toughness == 4
    assert CardType.LAND not in hall.card_types and Keyword.FLYING in hall.keywords
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.power == 4 and target.power == 3


def test_copy_does_not_copy_counters_or_damage_or_tapped_state():
    game, player, hall, target = arrange()
    add_counter(game, target, "+1/+1", 3)
    target.damage_marked = 2
    target.is_tapped = True
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.power == 3 and hall.damage_marked == 0 and not hall.is_tapped


def test_copy_preserves_own_tapped_state_and_counters():
    game, player, hall, _ = arrange()
    hall.is_tapped = True
    add_counter(game, hall, "charge", 2)
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.is_tapped and hall.counters.get("charge") == 2


def test_copy_expires_at_cleanup_and_land_works_again():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert hall.name == "Hall of Echoes" and hall.card_types == {CardType.LAND}
    activate_card_ability(game, player, hall, 1)
    assert player.mana_pool.total() == 1


def test_copy_target_leaves_before_resolution_fizzles():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    exile(game, target)
    resolve_stack(game)
    assert hall.card_types == {CardType.LAND}


def test_blinked_target_is_new_object():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, target, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert hall.name == "Hall of Echoes"


def test_hall_leaving_does_not_stop_legend_rule_suppression():
    game, player, hall, _target = arrange()
    activate_card_ability(game, player, hall)
    exile(game, hall)
    resolve_stack(game)
    one = enter_permanent(game, player, Creature(name="Twin", supertypes={Supertype.LEGENDARY}, base_power=2, base_toughness=2))
    two = enter_permanent(game, player, Creature(name="Twin", supertypes={Supertype.LEGENDARY}, base_power=2, base_toughness=2))
    resolve_stack(game)
    assert game.get_battlefield(player).contains(one) and game.get_battlefield(player).contains(two)
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    resolve_stack(game)
    assert len([c for c in game.get_battlefield(player).get_all() if c.name == "Twin"]) == 1


def test_legendary_copy_and_original_survive_this_turn():
    game, player, hall, target = arrange()
    target.supertypes = {Supertype.LEGENDARY}
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert game.get_battlefield(player).contains(hall) and game.get_battlefield(player).contains(target)


def test_copied_hall_leaves_as_its_printed_card():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    move_to_zone(game, hall, Zone.BATTLEFIELD, Zone.HAND)
    assert hall.name == "Hall of Echoes" and hall.card_types == {CardType.LAND}


def test_cannot_activate_without_five_mana():
    game, player, hall, _ = arrange()
    player.mana_pool.pay(ManaCost(generic=1))
    with pytest.raises(AbilityError):
        activate_card_ability(game, player, hall)
    assert player.mana_pool.total() == 4 and hall.name == "Hall of Echoes"


def test_opponents_creature_is_not_a_legal_target():
    game, player, hall, target = arrange()
    exile(game, target)
    enter_permanent(game, game.players[1], EchoCreature())
    with pytest.raises(AbilityError):
        activate_card_ability(game, player, hall)
    assert player.mana_pool.total() == 5


def test_old_land_can_attack_after_becoming_a_creature():
    from engine.combat import declare_attackers_step

    game, player, hall, _ = arrange()
    advance_game_to_phase(game, Phase.BEGINNING, Step.UNTAP)
    advance_game_to_phase(game, Phase.PRECOMBAT_MAIN)
    advance_game_to_phase(game, Phase.BEGINNING, Step.UNTAP)
    advance_game_to_phase(game, Phase.PRECOMBAT_MAIN)
    player.mana_pool.add(ManaType.COLORLESS, 5)
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    declare_attackers_step(game, [hall])
    assert hall.is_attacking


def test_copy_of_copy_uses_copiable_values_and_expires_independently():
    game, player, hall, target = arrange()
    second = enter_permanent(game, player, HallofEchoes())
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    add_counter(game, hall, "+1/+1", 3)
    prefer(player, object_preference(game, hall))
    player.mana_pool.add(ManaType.COLORLESS, 5)
    activate_card_ability(game, player, second)
    resolve_stack(game)
    assert second.name == target.name and second.power == 3 and hall.power == 6
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert hall.name == second.name == "Hall of Echoes"


def test_plus_one_counter_on_land_applies_while_copied_and_persists():
    game, player, hall, _ = arrange()
    add_counter(game, hall, "+1/+1", 2)
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.power == 5 and hall.toughness == 6
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    assert hall.counters.get("+1/+1") == 2


def test_copying_does_not_trigger_copied_enters_ability():
    from engine.events import EntersBattlefieldTriggeredEvent
    from engine.game import draw_card
    from engine.triggers import TriggerRegistration

    class Welcomer(Creature):
        def __init__(self, **kwargs):
            super().__init__(name="Welcomer", base_power=2, base_toughness=2, **kwargs)

        def register_triggers(self, game):
            game.trigger_manager.register(TriggerRegistration(
                EntersBattlefieldTriggeredEvent,
                lambda state, event: event.permanent is self,
                lambda state: draw_card(state, self.controller),
                self, self.controller,
            ))

    game, player, hall, _ = arrange()
    target = enter_permanent(game, player, Welcomer())
    resolve_stack(game)
    assert len(game.get_hand(player).get_all()) == 1
    prefer(player, object_preference(game, target))
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert hall.name == "Welcomer" and len(game.get_hand(player).get_all()) == 1


def test_illegal_target_prevents_legend_rule_suppression():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    exile(game, target)
    resolve_stack(game)
    for _ in range(2):
        enter_permanent(game, player, Creature(name="Twin", supertypes={Supertype.LEGENDARY}, base_power=2, base_toughness=2))
    resolve_stack(game)
    assert len([c for c in game.get_battlefield(player).get_all() if c.name == "Twin"]) == 1


def test_hall_blinked_in_response_is_not_copied():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall)
    move_to_zone(game, hall, Zone.BATTLEFIELD, Zone.EXILE)
    move_to_zone(game, hall, Zone.EXILE, Zone.BATTLEFIELD)
    resolve_stack(game)
    assert hall.name == "Hall of Echoes" and hall.card_types == {CardType.LAND}


def test_legend_rule_suppression_does_not_protect_opponent():
    game, player, hall, _ = arrange()
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    opponent = game.players[1]
    for _ in range(2):
        enter_permanent(game, opponent, Creature(name="Twin", supertypes={Supertype.LEGENDARY}, base_power=2, base_toughness=2))
    resolve_stack(game)
    assert len([c for c in game.get_battlefield(opponent).get_all() if c.name == "Twin"]) == 1


def test_copied_dies_trigger_fires_for_hall_without_killing_original():
    from cards.fdn.fdn_252.card_impl import GleamingBarrier
    from engine.game import sacrifice

    game, player, hall, _ = arrange()
    target = enter_permanent(game, player, GleamingBarrier())
    prefer(player, object_preference(game, target))
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    sacrifice(game, player, hall)
    resolve_stack(game)
    assert hall.name == "Hall of Echoes" and player.zones[Zone.GRAVEYARD].contains(hall)
    assert game.get_battlefield(player).contains(target)
    assert len([c for c in game.get_battlefield(player).get_all() if "Treasure" in c.subtypes]) == 1


def test_temporary_granted_keyword_is_not_copied():
    from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer

    game, player, hall, target = arrange()
    game.effect_manager.add(ContinuousEffect(
        target, Layer.ABILITY,
        apply=lambda state: setattr(target, "keywords", target.keywords | Keyword.HASTE),
        duration=DURATION_END_OF_TURN,
    ))
    game.effect_manager.apply_all(game)
    assert Keyword.HASTE in target.keywords
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    assert Keyword.HASTE not in hall.keywords
    assert Keyword.FLYING in hall.keywords


class ControlChange(Instant):
    def __init__(self, target, **kwargs):
        super().__init__(name="Control change", mana_cost=ManaCost(), **kwargs)
        self.target = target

    def on_resolve(self, game):
        from engine.continuous_effects import DURATION_END_OF_TURN, ContinuousEffect, Layer

        controller = self.controller

        def apply(state):
            for previous in state.players:
                if state.get_battlefield(previous).contains(self.target):
                    if previous is not controller:
                        state.get_battlefield(previous).remove(self.target)
                        state.get_battlefield(controller).add(self.target)
                    self.target.controller = controller
                    break

        game.effect_manager.add(ContinuousEffect(
            self, Layer.CONTROL, apply=apply, duration=DURATION_END_OF_TURN,
        ))

def test_stolen_target_is_illegal_when_copy_ability_resolves():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    cast_card(game, game.players[1], ControlChange(target))
    assert hall.name == "Hall of Echoes"
    assert target.controller is game.players[1]


def test_pending_copy_keeps_original_controller_for_legend_suppression():
    game, player, hall, target = arrange()
    activate_card_ability(game, player, hall)
    opponent = game.players[1]
    cast_card(game, opponent, ControlChange(hall))
    assert hall.controller is opponent and hall.name == target.name
    for controller in (player, opponent):
        for _ in range(2):
            enter_permanent(game, controller, Creature(
                name="Twin", supertypes={Supertype.LEGENDARY}, base_power=2, base_toughness=2,
            ))
    resolve_stack(game)
    assert len([c for c in game.get_battlefield(player).get_all() if c.name == "Twin"]) == 2
    assert len([c for c in game.get_battlefield(opponent).get_all() if c.name == "Twin"]) == 1


@pytest.mark.parametrize("haste", [False, True])
def test_new_hall_can_attack_only_if_copy_has_haste(haste):
    from engine.combat import declare_attackers_step

    game, player, hall, _ = arrange()
    target = enter_permanent(game, player, Creature(
        name="Attack copy", base_power=2, base_toughness=2,
        keywords=Keyword.HASTE if haste else Keyword(0),
    ))
    prefer(player, object_preference(game, target))
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    declare_attackers_step(game, [hall])
    assert hall.is_attacking is haste


def test_copied_recollector_prepares_and_casts_its_inset_spell():
    from cards.fra.fra_49.card_impl import BloodlineRecollector
    from engine.casting import cast_spell
    from engine.decisions import Decision
    from engine.game import sacrifice

    game, player, hall, _ = arrange()
    target = enter_permanent(game, player, BloodlineRecollector())
    prefer(player, object_preference(game, target))
    activate_card_ability(game, player, hall)
    resolve_stack(game)
    exile(game, target)
    for i in range(3):
        victim = enter_permanent(game, player, Creature(
            name=f"Victim {i}", base_power=1, base_toughness=1))
        sacrifice(game, player, victim)
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    spells = [c for c in player.zones[Zone.EXILE].get_all()
              if c.name == "Ancestral Craving"]
    assert len(spells) == 1
    player.mana_pool.add(ManaType.BLACK)
    prefer(player, Decision.player(seat=0))
    cast_spell(game, player, spells[0])
    resolve_stack(game)
    assert player.life == 17 and len(game.get_hand(player).get_all()) == 3
    assert game.get_battlefield(player).contains(hall)
    assert all(not player.zones[zone].contains(spells[0]) for zone in Zone)
