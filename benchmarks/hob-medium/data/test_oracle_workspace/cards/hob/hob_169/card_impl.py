from engine.card import Creature
from engine.types import ManaCost, Supertype


class TomBertAndWilliam(Creature):
    """Host-only reference implementation; see ADR-010."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Tom, Bert, and William",
            "mana_cost": ManaCost.parse("{3}{B}{G}"),
            "rules_text": "{1}, Sacrifice another creature: Draw cards equal to the sacrificed creature's power, then discard a card.\nWhen Tom, Bert, and William die, if they were a creature, return them to the battlefield. They're an artifact. (They're no longer a creature.)",
            "base_power": 5,
            "base_toughness": 5,
            "subtypes": {"Troll"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def get_activated_abilities(self):
        from engine.abilities import CostPayment
        from engine.card import ActivatedAbility
        from engine.card_queries import choose_object
        from engine.game import discard, draw_card, sacrifice
        from engine.hob_support import on_battlefield
        from engine.types import CardType

        def cost(g, source):
            player = source.controller
            candidates = [
                c
                for c in g.get_battlefield(player).get_all()
                if c is not source and CardType.CREATURE in c.card_types
            ]
            if not candidates or not player.mana_pool.can_pay(ManaCost(generic=1)):
                return False
            card = choose_object(
                g, player, candidates, "Sacrifice another creature", source_card=source
            )
            power = max(0, card.power)
            player.mana_pool.pay(ManaCost(generic=1))
            sacrifice(g, player, card)
            return CostPayment((player, power))

        def effect(g, paid):
            player, power = paid
            for _ in range(power):
                draw_card(g, player)
            hand = g.get_hand(player).get_all()
            if hand:
                card = choose_object(g, player, hand, "Discard a card", source_card=self)
                discard(g, player, card)

        return [
            ActivatedAbility(
                cost=cost,
                effect=effect,
                can_activate=lambda g, c, p: on_battlefield(g, c) and c.controller is p,
                description="Sacrifice another creature: draw its power, then discard",
            )
        ]

    def register_triggers(self, game):
        from engine.events import CreatureDiesTriggeredEvent
        from engine.hob_support import artifact_entry
        from engine.stack import object_stint_id
        from engine.triggers import TriggerRegistration
        from engine.types import CardType, Zone
        from engine.zones import move_to_zone

        def capture(g, event, controller):
            return object_stint_id(g, self)

        def effect(g, controller, stint):
            if (
                getattr(self, "is_token", False)
                or not self.owner.zones[Zone.GRAVEYARD].contains(self)
                or object_stint_id(g, self) != stint
            ):
                return
            self.controller = self.owner
            move_to_zone(g, self, Zone.GRAVEYARD, Zone.BATTLEFIELD, entry_transform=artifact_entry)

        game.trigger_manager.register(
            TriggerRegistration(
                CreatureDiesTriggeredEvent,
                lambda g, e: e.creature is self and CardType.CREATURE in self.card_types,
                effect,
                self,
                self.controller,
                capture=capture,
            )
        )
