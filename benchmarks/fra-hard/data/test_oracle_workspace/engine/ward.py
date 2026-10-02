"""Ward triggers are independent of the object that was targeted."""

from engine.card_queries import query_yes_no
from engine.stack import StackObject, move_spell_off_stack
from engine.types import Zone


def trigger_ward(game, stack_object):
    seen = set()
    for target in stack_object.targets or ():
        if id(target) in seen:
            continue
        seen.add(id(target))
        cost = getattr(target, "ward_cost", None)
        if not callable(cost) or target.controller is stack_object.controller:
            continue
        if not any(game.get_battlefield(player).contains(target) for player in game.players):
            continue
        payer = stack_object.controller

        def resolve(state, cost=cost, payer=payer, target=target):
            if not state.stack.contains(stack_object):
                return
            if query_yes_no(state, payer, "Pay ward?", source_card=target) and cost(state, payer):
                return
            move_spell_off_stack(state, stack_object, Zone.GRAVEYARD)

        game.stack.push(StackObject(source=target, controller=target.controller, on_resolve=resolve))
