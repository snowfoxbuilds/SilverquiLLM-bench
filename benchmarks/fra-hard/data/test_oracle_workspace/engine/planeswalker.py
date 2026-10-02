"""Empower tokens and continuous grants to planeswalkers."""

from engine.card import LoyaltyAbility, Planeswalker
from engine.card_queries import choose_object, query_yes_no
from engine.game import add_counter, create_token, deal_damage, draw_card, gain_life
from engine.types import CardType, Color, Zone
from engine.zones import move_to_zone


class JaceToken(Planeswalker):
    def __init__(self, **kwargs):
        super().__init__(name="Jace", subtypes={"Jace"}, starting_loyalty=0, **kwargs)
        self.colors = {Color.BLUE}

    def get_loyalty_abilities(self):
        controller = self.controller
        def surveil(game):
            player = controller
            library = game.get_library(player).get_all()
            if library and query_yes_no(game, player, "Put the surveilled card in your graveyard?", source_card=self):
                move_to_zone(game, library[-1], Zone.LIBRARY, Zone.GRAVEYARD)

        return [
            LoyaltyAbility(-1, surveil, "−1: Surveil 1."),
            LoyaltyAbility(-3, lambda game: draw_card(game, controller), "−3: Draw a card."),
        ]


def empower_jace(game, player, amount, source):
    tokens = [card for card in game.get_battlefield(player).get_all()
              if getattr(card, "is_token", False) and "Jace" in card.subtypes
              and CardType.PLANESWALKER in card.card_types]
    if not tokens:
        tokens = create_token(game, player, factory=lambda: JaceToken(owner=player))
    if not tokens:
        return
    target = choose_object(game, player, tokens, "Choose a Jace token to empower", source_card=source)
    add_counter(game, target, "loyalty", amount)


def granted_loyalty_abilities(card, game):
    if CardType.PLANESWALKER not in card.card_types:
        return []
    grants = []
    for source in game.get_battlefield(card.controller).get_all():
        if not getattr(source, "grants_drain_loyalty", False):
            continue
        controller = card.controller

        def drain(state, controller=controller):
            for opponent in state.players:
                if opponent is not controller:
                    deal_damage(state, card, opponent, 1)
            gain_life(state, controller, 1)

        grants.append(LoyaltyAbility(2, drain, "+2: This planeswalker deals 1 damage to each opponent and you gain 1 life."))
    return grants


def refresh_granted_abilities(game):
    for player in game.players:
        for card in game.get_battlefield(player).get_all():
            if not hasattr(card, "_printed_loyalty_method"):
                card._printed_loyalty_method = getattr(card, "get_loyalty_abilities", list)
                card.get_loyalty_abilities = lambda card=card: (
                    card._printed_loyalty_method() + granted_loyalty_abilities(card, game)
                )
