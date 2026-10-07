"""Empower tokens and continuous grants to planeswalkers."""

import inspect

from engine.card import LoyaltyAbility
from engine.card_queries import choose_object, query_yes_no
from engine.game import add_counter, create_token, deal_damage, draw_card, gain_life
from engine.types import CardType, Zone
from engine.zones import move_to_zone


def _jace_token(player):
    # The predefined token class lives with the cards, which the engine's own
    # tests do not load, so it is imported only when a token is created.
    from cards.fra.tokens import JaceToken, JaceTokenAbility1, JaceTokenAbility2

    class EmpoweredJace(JaceToken):
        printed_as = JaceToken

        def get_loyalty_abilities(self):
            controller = self.controller

            def surveil(game):
                library = game.get_library(controller).get_all()
                if library and query_yes_no(game, controller, "Put the surveilled card in your graveyard?",
                                            source_card=self):
                    move_to_zone(game, library[-1], Zone.LIBRARY, Zone.GRAVEYARD)

            return [
                LoyaltyAbility(-1, surveil, "−1: Surveil 1.", printed=JaceTokenAbility1),
                LoyaltyAbility(-3, lambda game: draw_card(game, controller), "−3: Draw a card.",
                               printed=JaceTokenAbility2),
            ]

    return EmpoweredJace(owner=player)


def empower_jace(game, player, amount, source):
    tokens = [card for card in game.get_battlefield(player).get_all()
              if getattr(card, "is_token", False) and "Jace" in card.subtypes
              and CardType.PLANESWALKER in card.card_types]
    if not tokens:
        tokens = create_token(game, player, factory=lambda: _jace_token(player))
    if not tokens:
        return
    target = choose_object(game, player, tokens, "Choose a Jace token to empower", source_card=source)
    add_counter(game, target, "loyalty", amount)


def granted_loyalty_abilities(card, game):
    if CardType.PLANESWALKER not in card.card_types:
        return []
    grants = []
    sources = [source for player in game.players for source in game.get_battlefield(player).get_all()]
    for source in sources:
        if not getattr(source, "grants_drain_loyalty", False) or source.controller is not card.controller:
            continue
        controller = card.controller

        def drain(state, controller=controller):
            for opponent in state.players:
                if opponent is not controller:
                    deal_damage(state, card, opponent, 1)
            gain_life(state, controller, 1)

        grants.append(LoyaltyAbility(
            2, drain, "+2: This planeswalker deals 1 damage to each opponent and you gain 1 life.",
            printed=getattr(source, "drain_loyalty_printed", None),
        ))
    return grants


def _listed(getter, game):
    return list(getter(game) if inspect.signature(getter).parameters else getter())


def _with_granted_abilities(card, game):
    printed_abilities = card._printed_loyalty_method

    def abilities():
        return _listed(printed_abilities, game) + granted_loyalty_abilities(card, game)

    return abilities


def refresh_granted_abilities(game):
    for player in game.players:
        for card in game.get_battlefield(player).get_all():
            if not hasattr(card, "_printed_loyalty_method"):
                card._printed_loyalty_method = getattr(card, "get_loyalty_abilities", lambda: [])
                card.get_loyalty_abilities = _with_granted_abilities(card, game)
