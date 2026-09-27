from engine.card import Instant
from engine.types import ManaCost


class TheEaglesAreComing(Instant):
    """Host-only reference implementation; see ADR-010."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "The Eagles Are Coming!",
            "mana_cost": ManaCost.parse("{1}{W}"),
            "rules_text": "Kicker {2}{W}{W} (You may pay an additional {2}{W}{W} as you cast this spell.)\nChoose target creature you own. If this spell was kicked, instead choose any number of target creatures you own. Return each chosen creature to your hand. At the beginning of the next upkeep, create a 4/4 white Bird Soldier creature token with flying for each creature returned to your hand this way.",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def prepare_cast(self, game, player):
        from engine.card_queries import query_yes_no

        self.kicked = query_yes_no(game, player, "Pay kicker {2}{W}{W}?", source_card=self)
        self.additional_cast_cost = ManaCost.parse("{2}{W}{W}") if self.kicked else ManaCost()

    def get_targets(self, game):
        from engine.types import CardType, TargetRequirement, Zone

        legal = lambda c: CardType.CREATURE in c.card_types and c.owner is self.controller
        count = sum(legal(c) for p in game.players for c in game.get_battlefield(p).get_all())
        return [
            TargetRequirement(legal, "creature you own", Zone.BATTLEFIELD, optional=self.kicked)
            for _ in range(count if self.kicked else 1)
        ]

    def on_resolve(self, game):
        from engine.card import Creature
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.game import create_token
        from engine.hob_support import delayed, on_battlefield
        from engine.protection import has_protection_from
        from engine.types import CardType, Color, Keyword, Zone
        from engine.zones import move_to_zone

        player = self.controller
        returned = 0
        for card in getattr(self, "chosen_targets", ()):
            if (
                card is not None
                and on_battlefield(game, card)
                and CardType.CREATURE in card.card_types
                and card.owner is player
                and not has_protection_from(card, self)
            ):
                move_to_zone(game, card, Zone.BATTLEFIELD, Zone.HAND)
                returned += int(player.zones[Zone.HAND].contains(card))
        if returned:

            def birds(g):
                def factory():
                    token = Creature(
                        name="Bird Soldier",
                        base_power=4,
                        base_toughness=4,
                        mana_cost=ManaCost(),
                        subtypes={"Bird", "Soldier"},
                        keywords=Keyword.FLYING,
                        owner=player,
                    )
                    token.colors = {Color.WHITE}
                    return token

                create_token(g, player, count=returned, factory=factory)

            delayed(game, BeginningOfUpkeepTriggeredEvent, player, birds)
