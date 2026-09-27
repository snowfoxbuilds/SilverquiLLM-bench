from engine.card import Creature
from engine.types import ManaCost, Supertype


class TheNotaryHobbits(Creature):
    """Host-only reference implementation; see ADR-010."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "The Notary Hobbits",
            "mana_cost": ManaCost.parse("{3}{G}{G}"),
            "rules_text": "When The Notary Hobbits enter, if they're not a token, create two tokens that are copies of them, except the tokens aren't legendary.\n{T}: Add {C} for each Halfling you control.",
            "base_power": 1,
            "base_toughness": 1,
            "subtypes": {"Halfling", "Advisor"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def register_triggers(self, game):
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.game import create_token, mint_token_copy
        from engine.triggers import TriggerRegistration

        def copies(g, controller):
            def factory():
                token = mint_token_copy(self)
                token.summoning_sick = True
                token.supertypes.discard(Supertype.LEGENDARY)
                return token

            create_token(g, controller, factory=factory, count=2)

        game.trigger_manager.register(
            TriggerRegistration(
                EntersBattlefieldTriggeredEvent,
                lambda g, e: e.permanent is self and not getattr(self, "is_token", False),
                copies,
                self,
                self.controller,
            )
        )

    def get_activated_abilities(self):
        from engine.card import ManaAbility
        from engine.hob_support import tap_for_mana
        from engine.types import ManaType

        def mana(g):
            controller = self.controller
            count = sum("Halfling" in c.subtypes for c in g.get_battlefield(controller).get_all())
            controller.mana_pool.add(ManaType.COLORLESS, count)

        return [
            ManaAbility(
                cost=tap_for_mana,
                mana_produced=mana,
                description="Add {C} for each Halfling you control",
            )
        ]

    def get_mana_abilities(self):
        return self.get_activated_abilities()
