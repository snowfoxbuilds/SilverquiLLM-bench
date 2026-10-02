from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.casting import grant_cast_permission
from engine.events import SpellCastTriggeredEvent
from engine.game import sacrifice, untap
from engine.mana_grants import end_exile_duration, grant_double_colorless
from engine.protection import has_protection_from
from engine.stack import surviving_targets
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.zones import move_to_zone


class EmrakultheExigentDoom(Creature):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Emrakul, the Exigent Doom',
            'mana_cost': ManaCost.parse('{10}'),
            'rules_text': 'When you cast this spell, untap all lands you control.\nFlying, trample\nWard—Sacrifice three permanents.\n{3}, Exile this card from your hand: Target land gains "{T}: Add {C}{C}" until this card is cast from exile. You may cast this card for as long as it remains exiled.',
            'base_power': 12,
            'base_toughness': 12,
            'subtypes': {'Eldrazi'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
        self.keywords = self._original_keywords = Keyword.FLYING | Keyword.TRAMPLE

    def on_cast(self, game):
        end_exile_duration(game, self)
        controller = self.controller

        def effect(state):
            for permanent in state.get_battlefield(controller).get_all():
                if CardType.LAND in permanent.card_types:
                    untap(state, permanent)

        game.trigger_manager.unregister(self)
        game.trigger_manager.register(TriggerRegistration(
            SpellCastTriggeredEvent, lambda state, event: event.card is self,
            effect, self, controller,
        ))

    def ward_cost(self, game, player):
        permanents = game.get_battlefield(player).get_all()
        if len(permanents) < 3:
            return False
        chosen = choose_object(game, player, permanents, "Sacrifice three permanents for ward",
                               source_card=self, min=3, max=3)
        for card in chosen:
            sacrifice(game, player, card)
        return True

    def get_activated_abilities(self):
        activation = {}
        def legal(state, source, player):
            return state.get_hand(player).contains(source) and source.owner is player

        def targeting(state, source, player):
            lands = [card for p in state.players for card in state.get_battlefield(p).get_all()
                     if CardType.LAND in card.card_types and not has_protection_from(card, self)
                     and not (card.controller is not player and Keyword.HEXPROOF in card.keywords)]
            if not lands:
                return None
            return [choose_object(state, player, lands, "Target land", source_card=self)]

        def cost(state, source):
            player = source.owner
            mana = ManaCost(generic=3)
            if not player.mana_pool.can_pay(mana):
                return False
            player.mana_pool.pay(mana)
            move_to_zone(state, self, Zone.HAND, Zone.EXILE)
            return True

        def effect(state, targets, context):
            targets = surviving_targets(state, context, targets,
                lambda card: CardType.LAND in card.card_types and not has_protection_from(card, self)
                and not (card.controller is not context.controller and Keyword.HEXPROOF in card.keywords))
            if not targets:
                return
            # The cost exiles this particular incarnation, even if it later leaves exile.
            epoch = activation["exile_epoch"]
            grant_double_colorless(state, targets[0], self, epoch)
            if self.owner.zones[Zone.EXILE].contains(self) and state.refs.zone_epoch(self) == epoch:
                grant_cast_permission(state, context.controller, self)

        def exile_cost(state, source):
            if not cost(state, source):
                return False
            activation["exile_epoch"] = state.refs.zone_epoch(self)
            return True

        return [ActivatedAbility(exile_cost, effect, "{3}, Exile this card from your hand", targeting, legal)]
