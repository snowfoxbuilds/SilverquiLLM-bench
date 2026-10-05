from engine import attempts
from engine.card import Creature
from engine.card_queries import choose_object
from engine.casting import CastingError, cast_spell_free
from engine.copying import copy_card
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import surviving_targets
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from engine.zones import move_to_zone


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class UldarosTheorixAbility1:
    text = 'Flying'


class UldarosTheorixAbility2:
    text = 'When Uldaros Theorix enters, if you cast him, exile up to one target nonland card of each card type from your graveyard. Copy those cards. You may cast any number of spells with total mana value 6 or less from among the copies without paying their mana costs. (Permanent spells cast this way become tokens.)'


# endregion Printed abilities


class UldarosTheorix(Creature):

    def __init__(self, **kwargs):
        defaults = {
            'name': 'Uldaros Theorix',
            'mana_cost': ManaCost.parse('{3}{U}{B}{B}'),
            'rules_text': 'Flying\nWhen Uldaros Theorix enters, if you cast him, exile up to one target nonland card of each card type from your graveyard. Copy those cards. You may cast any number of spells with total mana value 6 or less from among the copies without paying their mana costs. (Permanent spells cast this way become tokens.)',
            'base_power': 5,
            'base_toughness': 5,
            'subtypes': {'Elder', 'Sphinx'},
            'supertypes': {Supertype.LEGENDARY},
        }
        defaults.update(kwargs)
        super().__init__(**defaults)
        self.keywords = self._original_keywords = Keyword.FLYING

    def register_triggers(self, game):
        def targeting(state, event, player):
            selected = []
            for card_type in CardType:
                if card_type is CardType.LAND:
                    continue
                options = [card for card in player.zones[Zone.GRAVEYARD].get_all()
                    if card_type in card.card_types and CardType.LAND not in card.card_types
                    and card not in selected]
                target = choose_object(state, player, options,
                    f"Exile up to one {card_type.value} card", source_card=self, optional=True)
                if target is not None:
                    selected.append(target)
            return selected

        def effect(state, targets, context):
            player = context.controller
            valid = surviving_targets(state, context, targets,
                lambda card: player.zones[Zone.GRAVEYARD].contains(card) and CardType.LAND not in card.card_types)
            copies = []
            for card in valid:
                move_to_zone(state, card, Zone.GRAVEYARD, Zone.EXILE)
                if not player.zones[Zone.EXILE].contains(card):
                    continue
                spell = copy_card(card, player)
                player.zones[Zone.EXILE].add(spell)
                copies.append(spell)
            budget = [6]
            chosen = [None]

            def cast_one():
                options = [card for card in copies
                           if card.mana_cost.cmc <= budget[0] and card.can_cast(state)]
                chosen[0] = choose_object(state, player, options, "Cast a copied spell",
                                          source_card=self, optional=True)
                if chosen[0] is None:
                    return None
                cast_spell_free(state, player, chosen[0], Zone.EXILE, mana_value_limit=budget[0])
                return chosen[0]

            while copies:
                # Each cast is its own attempt: a rejected one is undone and asked
                # again (see ADR-017).
                try:
                    spell = attempts.attempt(state, cast_one)
                except CastingError:
                    # No player could have chosen differently: that copy cannot be cast.
                    failed = chosen[0]
                    copies.remove(failed)
                    for zone in (player.zones[value] for value in Zone):
                        if zone.contains(failed):
                            zone.remove(failed)
                    continue
                if spell is None:
                    break
                copies.remove(spell)
                budget[0] -= spell.mana_cost.cmc
            for spell in copies:
                if player.zones[Zone.EXILE].contains(spell):
                    player.zones[Zone.EXILE].remove(spell)

        game.trigger_manager.register(TriggerRegistration(
            EntersBattlefieldTriggeredEvent,
            lambda state, event: event.permanent is self and getattr(self, "was_cast", False),
            effect, self, self.controller, targeting=targeting, printed=UldarosTheorixAbility2,
        ))
