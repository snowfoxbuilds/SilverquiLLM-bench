from engine.card import Creature
from engine.types import ManaCost, Supertype


class GollumRiddleMaster(Creature):
    """Host-only reference implementation; see ADR-010."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Gollum, Riddle Master",
            "mana_cost": ManaCost.parse("{1}{B}"),
            "rules_text": "As Gollum enters, choose odd or even. (Zero is even.)\nWhenever an opponent casts a spell with mana value of the chosen quality, choose one that hasn't been chosen —\n• Put a +1/+1 counter on Gollum.\n• Each opponent loses 2 life and you gain 2 life.\n• Draw a card.",
            "base_power": 3,
            "base_toughness": 1,
            "subtypes": {"Halfling", "Horror"},
            "supertypes": {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def as_enters(self, game):
        from engine.card_queries import choose_mode
        from engine.game import remove_counter

        for kind, count in list(self.counters.items()):
            remove_counter(game, self, kind, count)
        self.parity = choose_mode(
            game, self.controller, ["odd", "even"], "Choose odd or even", source_card=self
        )
        self.chosen_modes = set()

    def register_triggers(self, game):
        from engine.card_queries import choose_mode
        from engine.events import SpellCastTriggeredEvent
        from engine.game import add_counter, draw_card, gain_life, lose_life
        from engine.hob_support import on_battlefield
        from engine.stack import object_stint_id
        from engine.triggers import TriggerRegistration

        modes = ["counter", "drain", "draw"]

        def eligible(g, event):
            card = event.card
            if card is None:
                return False
            value = event.mana_value if event.mana_value is not None else card.mana_cost.cmc
            return (
                event.player is not self.controller
                and card is not None
                and value % 2 == (1 if self.parity == "odd" else 0)
                and len(self.chosen_modes) < len(modes)
            )

        def capture(g, event, controller):
            mode = choose_mode(
                g,
                controller,
                [m for m in modes if m not in self.chosen_modes],
                "Choose an unused mode",
                source_card=self,
            )
            self.chosen_modes.add(mode)
            return mode, object_stint_id(g, self)

        def effect(g, controller, captured):
            mode, stint = captured
            if mode == "counter":
                if on_battlefield(g, self) and object_stint_id(g, self) == stint:
                    add_counter(g, self, "+1/+1", 1)
            elif mode == "drain":
                for opponent in g.players:
                    if opponent is not controller:
                        lose_life(g, opponent, 2)
                gain_life(g, controller, 2)
            else:
                draw_card(g, controller)

        game.trigger_manager.register(
            TriggerRegistration(
                SpellCastTriggeredEvent, eligible, effect, self, self.controller, capture=capture
            )
        )
