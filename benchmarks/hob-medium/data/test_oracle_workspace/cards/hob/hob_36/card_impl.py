from engine.card import Creature
from engine.types import ManaCost, Supertype


class ElrondMoonReader(Creature):
    """Host-only reference implementation; see ADR-010."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Elrond, Moon-Reader",
            "mana_cost": ManaCost.parse("{2}{U}"),
            "rules_text": "Whenever you activate an ability of a creature, draw a card. This ability triggers only once each turn.\n{5}{U}{U}: Exile up to two other target nonland permanents you control. Return those cards to the battlefield under their owner's control at the beginning of the next end step.",
            "base_power": 3,
            "base_toughness": 3,
            "subtypes": {"Elf", "Noble"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def as_enters(self, game):
        self.last_activation_turn = None

    def register_triggers(self, game):
        from engine.events import AbilityActivatedTriggeredEvent
        from engine.game import draw_card
        from engine.triggers import TriggerRegistration

        def eligible(g, event):
            if (
                event.controller is not self.controller
                or not event.was_creature
                or self.last_activation_turn == g.turn_number
            ):
                return False
            self.last_activation_turn = g.turn_number
            return True

        game.trigger_manager.register(
            TriggerRegistration(
                AbilityActivatedTriggeredEvent,
                eligible,
                lambda g, controller: draw_card(g, controller),
                self,
                self.controller,
            )
        )

    def get_activated_abilities(self):
        from engine.card import ActivatedAbility
        from engine.events import EndStepTriggeredEvent
        from engine.game import exile
        from engine.hob_support import choose_targets, delayed, on_battlefield, return_from_exile
        from engine.stack import object_stint_id, surviving_targets
        from engine.types import CardType

        def legal(c, controller):
            return (
                c is not self and c.controller is controller and CardType.LAND not in c.card_types
            )

        def targeting(g, source, controller):
            return choose_targets(g, source, controller, lambda c: legal(c, controller), 2)

        def effect(g, targets, context):
            tracked = []
            for card in surviving_targets(g, context, targets):
                if on_battlefield(g, card) and legal(card, context.controller):
                    exile(g, card)
                    tracked.append((card, object_stint_id(g, card)))
            if tracked:
                delayed(
                    g,
                    EndStepTriggeredEvent,
                    context.controller,
                    lambda state: return_from_exile(state, tracked),
                )

        return [
            ActivatedAbility(
                cost=lambda g, source: source.controller.mana_pool.pay(ManaCost.parse("{5}{U}{U}")),
                effect=effect,
                targeting=targeting,
                can_activate=lambda g, source, p: (
                    on_battlefield(g, source) and source.controller is p
                ),
                description="Exile up to two other nonland permanents; return next end step",
            )
        ]
